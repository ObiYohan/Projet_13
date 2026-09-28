import asyncio
from functools import partial
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .embedding_service import EmbeddingService
from .language import detect_language, requested_count
from .milvus_service import MilvusService
from .youtube_service import YouTubeService, YouTubeServiceError

DEFAULT_OPENINGS = 5
MAX_OPENINGS = 10
DEFAULT_LANGUAGE = "fr"
VIDEOS_PER_OPENING = 3
# An opening has up to ~4 chunks (EN + FR): fetch enough of them to find N distinct openings.
CHUNKS_PER_OPENING = 6
LANGUAGE_LABELS = {"fr": "en français", "en": "en anglais"}


class VectorSearchState(TypedDict, total=False):
    query: str
    top_k: int | None
    with_videos: bool
    requested_lang: str | None
    eco: str | None
    lang: str
    limit: int
    query_vector: list[float]
    hits: list[dict]
    results: list[dict]
    videos_message: str | None


class VectorSearchGraph:
    """LangGraph pipeline: analyse the question (language, number of openings
    asked for), search Milvus, keep one result per opening, then suggest up to
    VIDEOS_PER_OPENING YouTube videos per opening in the question's language."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        milvus_service: MilvusService,
        youtube_service: YouTubeService,
    ) -> None:
        self._embeddings = embedding_service
        self._milvus = milvus_service
        self._youtube = youtube_service
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(VectorSearchState)
        graph.add_node("analyze_query", self._analyze_query)
        graph.add_node("embed_query", self._embed_query)
        graph.add_node("search_milvus", self._search_milvus)
        graph.add_node("select_openings", self._select_openings)
        graph.add_node("suggest_videos", self._suggest_videos)
        graph.add_edge(START, "analyze_query")
        graph.add_edge("analyze_query", "embed_query")
        graph.add_edge("embed_query", "search_milvus")
        graph.add_edge("search_milvus", "select_openings")
        graph.add_conditional_edges(
            "select_openings", self._route_after_results, {"videos": "suggest_videos", "done": END}
        )
        graph.add_edge("suggest_videos", END)
        return graph.compile()

    async def _analyze_query(self, state: VectorSearchState) -> dict:
        query = state["query"]
        limit = state.get("top_k") or requested_count(query) or DEFAULT_OPENINGS
        return {
            "lang": state.get("requested_lang") or detect_language(query) or DEFAULT_LANGUAGE,
            "limit": max(1, min(limit, MAX_OPENINGS)),
        }

    async def _embed_query(self, state: VectorSearchState) -> dict:
        vector = await asyncio.to_thread(self._embeddings.embed_query, state["query"])
        return {"query_vector": vector}

    async def _search_milvus(self, state: VectorSearchState) -> dict:
        # An imposed language also applies to the passages; a detected one only
        # to the videos (a French question may be best answered by an English passage).
        search = partial(
            self._milvus.search,
            state["query_vector"],
            state["limit"] * CHUNKS_PER_OPENING,
            state.get("requested_lang"),
        )
        # A known ECO code picks the opening's own passages; semantic search
        # only when the corpus has none for that code.
        hits = await asyncio.to_thread(search, state["eco"]) if state.get("eco") else []
        if not hits:
            hits = await asyncio.to_thread(search)
        return {"hits": hits}

    async def _select_openings(self, state: VectorSearchState) -> dict:
        """One result per opening, ranked by its best chunk (hits come sorted by
        score); its description gathers its chunks found in that chunk's language."""
        by_opening: dict[tuple, list[dict]] = {}
        for hit in state["hits"]:
            by_opening.setdefault((hit.get("eco_code"), hit.get("opening_name")), []).append(hit)

        results = []
        for hits in by_opening.values():
            hit = hits[0]
            passages = sorted((h for h in hits if h.get("lang") == hit.get("lang")), key=lambda h: h["id"])
            results.append({
                "opening_name": hit.get("opening_name"),
                "opening_name_fr": hit.get("opening_name_fr"),
                "lang": hit.get("lang"),
                "eco_code": hit.get("eco_code"),
                "moves_san": hit.get("moves_san"),
                "source_url": hit.get("source_url"),
                "description_url": hit.get("description_url"),
                "text": hit.get("text"),
                # Chunks start with a header (names, ECO code, moves): keep their body.
                "description": "\n\n".join(p["text"].split("\n\n", 1)[-1] for p in passages),
                "score": hit.get("score"),
                "videos": [],
            })
            if len(results) == state["limit"]:
                break
        return {"results": results}

    @staticmethod
    def _route_after_results(state: VectorSearchState) -> str:
        return "videos" if state["results"] and state.get("with_videos", True) else "done"

    async def _suggest_videos(self, state: VectorSearchState) -> dict:
        lang = state["lang"]
        found = await asyncio.gather(
            *(self._find_videos(result, lang) for result in state["results"]), return_exceptions=True
        )
        results, missing, error = [], [], None
        for result, outcome in zip(state["results"], found):
            if isinstance(outcome, YouTubeServiceError):
                error = error or str(outcome)
                outcome = []
            elif isinstance(outcome, BaseException):
                raise outcome
            if not outcome:
                missing.append(self._display_name(result, lang))
            results.append({**result, "videos": outcome})

        message = error
        if not message and missing:
            names = ", ".join(f"« {name} »" for name in missing)
            message = f"Aucune vidéo pertinente {LANGUAGE_LABELS[lang]} trouvée pour {names}."
        return {"results": results, "videos_message": message}

    async def _find_videos(self, result: dict, lang: str) -> list[dict]:
        name = self._display_name(result, lang)
        aliases = tuple(n for n in (result["opening_name"], result.get("opening_name_fr")) if n and n != name)
        found = await asyncio.to_thread(
            self._youtube.search_videos, name, VIDEOS_PER_OPENING, lang, aliases
        )
        return found["videos"]

    @staticmethod
    def _display_name(result: dict, lang: str) -> str:
        if lang == "fr" and result.get("opening_name_fr"):
            return result["opening_name_fr"]
        return result["opening_name"]

    async def run(
        self,
        query: str,
        top_k: int | None = None,
        with_videos: bool = True,
        lang: str | None = None,
        eco: str | None = None,
    ) -> dict:
        final_state = await self._graph.ainvoke({
            "query": query,
            "top_k": top_k,
            "with_videos": with_videos,
            "requested_lang": lang,
            "eco": eco,
        })
        return {
            "lang": final_state["lang"],
            "results": final_state["results"],
            "videos_message": final_state.get("videos_message"),
        }
