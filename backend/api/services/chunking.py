"""Chunking service: split openings' descriptions into self-contained chunks of text

"""

MAX_CHUNK_CHARS = 800

DESCRIPTION_FIELDS = {
    "en": ("description", "description_url"),
    "fr": ("description_fr", "description_fr_url"),
}

def build_opening_chunks(record: dict) -> list[dict]:
    """Split an opening's English and French descriptions into self-contained
    chunks ({lang, text, url}): each one starts with the opening's names in both
    languages, its ECO code and moves, followed by paragraphs of one description."""
    names = record["opening_name"]
    if record.get("opening_name_fr"):
        names = f"{record['opening_name_fr']} ({record['opening_name']})"
    header = (
        f"Ouverture d'échecs : {names}, code ECO {record['eco_code']}. "
        f"Coups : {record['moves_san']}."
    )

    chunks = []
    for lang, (text_field, url_field) in DESCRIPTION_FIELDS.items():
        paragraphs = [p.strip() for p in record.get(text_field, "").split("\n\n") if p.strip()]
        for group in _group_paragraphs(paragraphs):
            chunks.append({"lang": lang, "text": f"{header}\n\n{group}", "url": record.get(url_field, "")})
    return chunks or [{"lang": "fr", "text": header, "url": record.get("source_url", "")}]


def _group_paragraphs(paragraphs: list[str]) -> list[str]:
    groups, current = [], ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) > MAX_CHUNK_CHARS:
            groups.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        groups.append(current)
    return groups
