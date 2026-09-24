import asyncio
from typing import Literal

from fastapi import FastAPI, HTTPException, Query

from .schemas import EvaluationResponse, MovesResponse, VectorSearchResponse, VideosResponse
from .services.chess_agent import ChessAgentService
from .services.embedding_service import EmbeddingService
from .services.lichess_service import (
    LichessRateLimitError,
    LichessServiceError,
    LichessTimeoutError,
)
from .services.milvus_service import MilvusService, MilvusServiceError
from .services.rag_graph import VectorSearchGraph
from .services.stockfish_service import StockfishServiceError
from .services.youtube_service import (
    YouTubeConfigError,
    YouTubeQuotaError,
    YouTubeService,
    YouTubeServiceError,
    YouTubeTimeoutError,
    no_videos_message,
)

app = FastAPI(title="Chess Agent API")
agent = ChessAgentService()
youtube = YouTubeService()
vector_search = VectorSearchGraph(EmbeddingService(), MilvusService(), youtube)


@app.get("/api/v1/healthcheck")
def healthcheck():
    return {"status": "ok"}


@app.get("/api/v1/moves/{fen:path}", response_model=MovesResponse)
async def get_moves(fen: str):
    """Theoretical moves for `fen` from the Lichess masters database."""
    try:
        return await agent.get_theoretical_moves(fen)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LichessTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LichessRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except LichessServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/evaluate/{fen:path}", response_model=EvaluationResponse)
async def get_evaluation(fen: str):
    """Stockfish evaluation of `fen`, in centipawns from white's point of view."""
    try:
        return await agent.evaluate_position(fen)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StockfishServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/vector-search", response_model=VectorSearchResponse)
async def vector_search_endpoint(
    query: str,
    top_k: int | None = Query(None, ge=1, le=10),
    with_videos: bool = True,
):
    """Semantic search over the openings indexed in Milvus: one result per
    opening (`top_k`, else the number asked for in the question, else 5), each
    with a YouTube video in the question's language (French or English)."""
    try:
        found = await vector_search.run(query, top_k, with_videos)
    except MilvusServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"query": query, **found}


@app.get("/api/v1/videos/{opening}", response_model=VideosResponse)
async def get_videos(
    opening: str,
    max_results: int = Query(5, ge=1, le=10),
    lang: Literal["fr", "en"] | None = None,
):
    """Relevant, embeddable YouTube videos explaining `opening`; with `lang`,
    only videos in that language."""
    try:
        found = await asyncio.to_thread(youtube.search_videos, opening, max_results, lang)
    except YouTubeConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except YouTubeQuotaError as exc:
        raise HTTPException(
            status_code=429, detail=str(exc), headers={"Retry-After": str(exc.retry_after)}
        ) from exc
    except YouTubeTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except YouTubeServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "opening": opening,
        "query": found["query"],
        "videos": found["videos"],
        "message": None if found["videos"] else no_videos_message(opening),
    }
