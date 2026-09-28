"""Build data/openings.json from Wikipedia, in English and French.

Sources:
- https://en.wikipedia.org/wiki/List_of_ECO_codes : ECO codes, moves and the
  article of each named opening.
- English articles (introduction, or the variation's section) for `description`.
- The French version of those articles, found through Wikipedia's
  interlanguage links, for `opening_name_fr` / `description_fr`. When the
  English description comes from a section, the French section is given
  explicitly in FRENCH_ARTICLES (headings differ between languages).
  The French ECO list (Liste des ouvertures d'échecs suivant le code ECO) was
  used to check names and section choices, but its names are too irregular
  ("partie ou ouverture anglaise jusqu'à A39") to be parsed automatically.

The hand-made entries of data/openings_seed.json are merged with the ECO list.
Openings without a reliable French description are dropped.

Run from the repository root (optional argument: output path):
    uv run --no-project --with httpx --with chess python scripts/build_openings_corpus.py
"""

import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote

import chess
import httpx

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "openings_seed.json"
OPENINGS_PATH = ROOT / "data" / "openings.json"

HEADERS = {"User-Agent": "Projet13-ChessRAG/0.1 (educational project)"}
EN_API = "https://en.wikipedia.org/w/api.php"
FR_API = "https://fr.wikipedia.org/w/api.php"
ECO_LIST_EN = "List of ECO codes"
ECO_URL = "https://en.wikipedia.org/wiki/List_of_ECO_codes"
MAX_DESCRIPTION_CHARS = 1500

# Below this size an article's introduction is too thin to give context: the
# beginning of the article's body is used instead.
MIN_INTRO_CHARS = 400

# Sections after which an article only holds references and navigation.
END_SECTIONS = [
    "See also", "Notes", "References", "Citations", "Sources", "Bibliography",
    "Further reading", "External links", "Voir aussi", "Références",
    "Bibliographie", "Liens externes", "Articles connexes",
]

# English article (and section) for entries added by hand, and for ECO rows
# whose link anchor doesn't match the article's section title.
ENGLISH_ARTICLES = {
    ("B54", "Sicilian"): ("Sicilian Defence", "Open Sicilian"),
    ("A40", "Queen's pawn"): ("Queen's Pawn Game", None),
    ("A80", "Dutch"): ("Dutch Defence", None),
    ("C00", "French defense"): ("French Defence", None),
    ("C13", "French : Classical"): ("French Defence", "Classical Variation"),
    ("C46", "Four knights game"): ("Four Knights Game", None),
    ("C60", "Ruy Lopez (Spanish Opening)"): ("Ruy Lopez", None),
    ("B97", "Najdorf Sicilian, Poisoned Pawn Variation"): ("Poisoned Pawn Variation", "Sicilian Defense, Najdorf"),
    ("C40", "King's Knight Opening"): ("Open Game", "2.Nf3 Nc6"),
    ("C48", "Four Knights Game, Spanish Variation"): ("Four Knights Game", "Double Spanish Variation"),
}

# French article, section heading (prefix, None for the introduction) and name,
# when interlanguage links can't be used: the English description comes from a
# section, or the English article has no French version.
FRENCH_ARTICLES = {
    ("B54", "Sicilian"): ("Défense sicilienne", "Variantes ouvertes", "Défense sicilienne, variantes ouvertes"),
    ("C13", "French : Classical"): ("Défense française", "La variante classique", "Défense française, variante classique"),
    ("A20", "Reversed Sicilian"): ("Ouverture anglaise", "Sicilienne inversée", "Ouverture anglaise, sicilienne inversée"),
    ("A30", "Symmetrical English"): ("Ouverture anglaise", "Anglaise symétrique", "Ouverture anglaise symétrique"),
    ("A60", "Modern Benoni"): ("Défense Benoni", "Défense Benoni moderne", "Défense Benoni moderne"),
    ("B97", "Najdorf Sicilian, Poisoned Pawn Variation"): ("Variante du pion empoisonné", None, "Variante du pion empoisonné"),
    ("C02", "French Defence, Advance Variation"): ("Défense française", "La variante d'avance", "Défense française, variante d'avance"),
    ("C03", "French Defence, Tarrasch Variation"): ("Défense française", "La variante Tarrasch", "Défense française, variante Tarrasch"),
    ("C15", "French Defence, Winawer Variation"): ("Défense française", "La variante Winawer", "Défense française, variante Winawer"),
    ("C47", "Four Knights Game, Scotch Variation"): ("Partie des quatre cavaliers", "4.d4 variante écossaise", "Partie des quatre cavaliers, variante écossaise"),
    ("C48", "Four Knights Game, Spanish Variation"): ("Partie des quatre cavaliers", "4.Fb5 variante espagnole", "Partie des quatre cavaliers, variante espagnole"),
    ("D96", "Grünfeld Defence, Russian System"): ("Défense Grünfeld", "Le système russe", "Défense Grünfeld, système russe"),
}

# Too generic ("Open Game", "Closed Game") to find a dedicated description or video.
EXCLUDED_ECO_CODES = {"C20", "D00"}

# D70's row has no fixed move sequence ("with d7–d5"): use D80's main line.
EXTRA_ECO_ROWS = [
    {"eco_code": "D80", "opening_name": "Grünfeld Defence",
     "moves": "1.d4 Nf6 2.c4 g6 3.Nc3 d5", "article": "Grünfeld Defence"},
]


# --- Wikipedia API --------------------------------------------------------

def api(url: str, params: dict) -> dict:
    for attempt in range(5):
        time.sleep(1.5)
        response = httpx.get(url, params={"format": "json", **params}, headers=HEADERS, timeout=30)
        if response.status_code == 429:
            time.sleep(float(response.headers.get("Retry-After", 10 * (attempt + 1))))
            continue
        response.raise_for_status()
        return response.json()
    response.raise_for_status()


def wikitext(url: str, title: str) -> str:
    data = api(url, {"action": "parse", "page": title, "prop": "wikitext", "formatversion": 2})
    return data["parse"]["wikitext"]


def fetch_intros(url: str, titles: list[str]) -> tuple[dict, dict]:
    """Return ({requested title: (resolved title, fragment)}, {resolved title: intro})."""
    resolved, intros = {}, {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        data = api(url, {"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
                         "redirects": 1, "titles": "|".join(batch)})["query"]
        normalized = {n["from"]: n["to"] for n in data.get("normalized", [])}
        redirects = {r["from"]: (r["to"], r.get("tofragment")) for r in data.get("redirects", [])}
        for title in batch:
            name = normalized.get(title, title)
            resolved[title] = redirects.get(name, (name, None))
        for page in data["pages"].values():
            intros[page["title"]] = page.get("extract", "")
    return resolved, intros


def fetch_french_titles(en_titles: list[str]) -> dict[str, str]:
    french = {}
    for i in range(0, len(en_titles), 50):
        batch = en_titles[i:i + 50]
        data = api(EN_API, {"action": "query", "prop": "langlinks", "lllang": "fr",
                            "lllimit": "max", "titles": "|".join(batch)})["query"]
        for page in data["pages"].values():
            for link in page.get("langlinks", []):
                french[page["title"]] = link["*"]
    return french


_full_articles: dict[tuple[str, str], str] = {}


def full_article(url: str, title: str) -> str:
    if (url, title) not in _full_articles:
        data = api(url, {"action": "query", "prop": "extracts", "explaintext": 1,
                         "exsectionformat": "wiki", "redirects": 1, "titles": title})["query"]
        _full_articles[(url, title)] = next(iter(data["pages"].values())).get("extract", "")
    return _full_articles[(url, title)]


def describe(url: str, page: str, heading: str | None, intro: str) -> tuple[str, str | None]:
    """Return (description, heading used) for an article's section or introduction."""
    if not heading:
        text = clean(intro)
        if len(text) < MIN_INTRO_CHARS:
            body = full_article(url, page)
            end = re.search(rf"^=+\s*({'|'.join(END_SECTIONS)})\b.*$", body, flags=re.M | re.I)
            text = clean(body[: end.start()] if end else body)
        return text, None

    wanted = fold(heading.replace("_", " "))
    text = full_article(url, page)
    for match in re.finditer(r"^(=+)\s*(.*?)\s*\1\s*$", text, flags=re.M):
        if fold(match.group(2)).startswith(wanted):
            level = len(match.group(1))
            rest = text[match.end():]
            end = re.search(rf"^={{1,{level}}}[^=].*?=+\s*$", rest, flags=re.M)
            return clean(rest[: end.start()] if end else rest), match.group(2)
    return "", None


def page_url(lang: str, title: str, fragment: str | None = None) -> str:
    url = f"https://{lang}.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))
    return url + ("#" + quote(fragment.replace(" ", "_")) if fragment else "")


# --- Text helpers ---------------------------------------------------------

def strip_markup(text: str) -> str:
    text = re.sub(r"<ref[^>]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\{\{(?!br\}\})[^{}]*\}\}", "", text)
    return text


def to_san(moves: str) -> str | None:
    """Parse a move sequence and return it as '1. e4 c5 2. Nf3', or None if illegal."""
    moves = moves.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
    tokens = re.sub(r"\d+\.(\.\.)?", " ", moves).split()
    board = chess.Board()
    out = []
    try:
        for token in tokens:
            move = board.parse_san(re.sub(r"[?!]+$", "", token))
            prefix = f"{board.fullmove_number}. " if board.turn == chess.WHITE else ""
            out.append(prefix + board.san(move))
            board.push(move)
    except ValueError:
        return None
    return " ".join(out) or None


def clean(text: str) -> str:
    """Plain-text extract -> short description: headings dropped, one-move-per-line
    blocks joined, pronunciation leftovers removed, cut on paragraph boundaries."""
    text = re.sub(r"^=+[^=\n]*=+\s*$", "", text, flags=re.M)
    lines, moves = [], []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^\d+\.\s*\S", line) and len(line) < 40:
            moves.append(line)
            continue
        if moves:
            lines.append(" ".join(moves))
            moves = []
        lines.append(line)
    if moves:
        lines.append(" ".join(moves))
    text = "\n".join(lines)
    text = re.sub(r"\(\s[^()]*\)|\(\s*\)|\(\s*;\s*", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([.,;:])", r"\1", text)
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    kept, size = [], 0
    for paragraph in paragraphs:
        if kept and size + len(paragraph) > MAX_DESCRIPTION_CHARS:
            break
        kept.append(paragraph)
        size += len(paragraph)
    return "\n\n".join(kept)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower().replace("’", "'").replace("\xa0", " "))
    return "".join(c for c in text if not unicodedata.combining(c))


def parse_eco_list(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        match = re.match(r"^\|\s*([A-E]\d\d)\s*\|\|(.*)\|\|(.*)$", line)
        if not match:
            continue
        code, moves, article = match.groups()
        article = strip_markup(article).split("{{br}}")[0]
        link = re.search(r"\[\[([^|\]]+)(?:\|([^\]]*))?\]\]", article)
        if not link:
            continue
        rows.append({"eco_code": code, "opening_name": (link.group(2) or link.group(1)).strip(),
                     "moves": strip_markup(moves).split("{{br}}")[0],
                     "article": link.group(1).strip()})
    return rows + EXTRA_ECO_ROWS


# --- Pipeline -------------------------------------------------------------

def build(output_path: Path) -> None:
    records = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    seen, en_targets = {r["moves_san"] for r in records}, {}
    for row in sorted(parse_eco_list(wikitext(EN_API, ECO_LIST_EN)), key=lambda r: r["eco_code"]):
        moves = to_san(row["moves"])
        if not moves or moves in seen or row["eco_code"] in EXCLUDED_ECO_CODES:
            continue
        seen.add(moves)
        records.append({"eco_code": row["eco_code"], "opening_name": row["opening_name"],
                        "moves_san": moves, "source_url": ECO_URL})
        title, _, fragment = row["article"].partition("#")
        en_targets[(row["eco_code"], row["opening_name"])] = (title, fragment or None)
    en_targets.update(ENGLISH_ARTICLES)

    # English descriptions.
    resolved, intros = fetch_intros(EN_API, sorted({t for t, _ in en_targets.values()}))
    for record in records:
        key = (record["eco_code"], record["opening_name"])
        title, fragment = en_targets[key]
        page, redirect_fragment = resolved.get(title, (title, None))
        fragment = fragment or redirect_fragment
        record["description"], _ = describe(EN_API, page, fragment, intros.get(page, ""))
        record["description_url"] = page_url("en", page, fragment)
        record["_en_page"], record["_en_section"] = page, bool(fragment)

    # French names and descriptions.
    fr_titles = fetch_french_titles(sorted({r["_en_page"] for r in records if not r["_en_section"]}))
    targets = {}
    for record in records:
        key = (record["eco_code"], record["opening_name"])
        if key in FRENCH_ARTICLES:
            targets[key] = FRENCH_ARTICLES[key]
        elif not record["_en_section"] and record["_en_page"] in fr_titles:
            targets[key] = (fr_titles[record["_en_page"]], None, None)
    fr_resolved, fr_intros = fetch_intros(FR_API, sorted({t for t, _, _ in targets.values()}))
    for record in records:
        key = (record["eco_code"], record["opening_name"])
        if key not in targets:
            continue
        title, heading, name = targets[key]
        page = fr_resolved.get(title, (title, None))[0]
        description, used_heading = describe(FR_API, page, heading, fr_intros.get(page, ""))
        if description:
            record["opening_name_fr"] = name or page
            record["description_fr"] = description
            record["description_fr_url"] = page_url("fr", page, used_heading)

    # Keep openings described in both languages, without duplicated descriptions.
    kept, dropped = [], []
    for record in records:
        label = f"{record['eco_code']} {record['opening_name']}"
        if not record.get("description"):
            dropped.append((label, "no English description"))
        elif not record.get("description_fr"):
            dropped.append((label, "no French description"))
        elif any(record["description_fr"] == k["description_fr"] for k in kept):
            dropped.append((label, "same French description as another entry"))
        else:
            kept.append({k: v for k, v in record.items() if not k.startswith("_")})

    output_path.write_text(json.dumps(kept, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(kept)} opening(s) written to {output_path}, {len(dropped)} dropped:")
    for label, reason in dropped:
        print(f"  - {label}: {reason}")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else OPENINGS_PATH)
