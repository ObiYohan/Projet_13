"""Lightweight French / English detection and request parsing, based on
frequent words: enough to choose between the two languages the app supports."""

import re
import unicodedata

FRENCH_WORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "est", "que", "qui", "quel",
    "quelle", "quels", "quelles", "pour", "avec", "dans", "sur", "pas", "moi", "donne",
    "donnes", "donnez", "ouverture", "ouvertures", "echecs", "noirs", "blancs", "comment",
    "pourquoi", "exemple", "exemples", "je", "tu", "il", "ce", "cette", "ou", "au", "aux",
    "partie", "defense", "variante", "coup", "coups", "explication", "explique", "apprendre",
}
ENGLISH_WORDS = {
    "the", "an", "of", "and", "is", "are", "what", "which", "how", "why", "for", "with",
    "in", "to", "me", "give", "opening", "openings", "chess", "black", "white",
    "example", "examples", "i", "you", "it", "this", "that", "best", "called", "game",
    "defense", "defence", "variation", "move", "moves", "explained", "learn", "play",
}

NUMBERS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
    "huit": 8, "neuf": 9, "dix": 10, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
COUNTED_NOUNS = (
    r"ouvertures?|exemples?|examples?|openings?|defenses?|defences?|gambits?|"
    r"suggestions?|variantes?|variations?|idees?|ideas?|parties?|games?"
)
COUNT_PATTERN = re.compile(
    rf"\b({'|'.join(NUMBERS)}|\d{{1,2}})\s+(?:[\w']+\s+){{0,2}}?(?:{COUNTED_NOUNS})\b"
)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def detect_language(text: str) -> str | None:
    """Return "fr", "en", or None when the text gives no clue."""
    words = re.findall(r"[a-z]+", _fold(text))
    french = sum(w in FRENCH_WORDS for w in words) + 2 * len(re.findall(r"[éèêàâçùûîôœ]", text.lower()))
    english = sum(w in ENGLISH_WORDS for w in words)
    if french == english:
        return None
    return "fr" if french > english else "en"


# Not "Italian", "Spanish", "Russian", "Portuguese": they also name openings.
OTHER_LANGUAGE_NAMES = {
    "hindi", "urdu", "tamil", "telugu", "bengali", "bangla", "marathi", "punjabi", "espanol",
    "portugues", "deutsch", "german", "italiano", "turkce", "turkish", "arabic", "indonesia",
    "indonesian", "vietnamese", "filipino", "tagalog",
}


def mentions_other_language(title: str) -> bool:
    """True for titles announcing another language ("... in Hindi", "en español")."""
    return bool(OTHER_LANGUAGE_NAMES & set(re.findall(r"[a-z]+", _fold(title))))


def has_non_latin_letters(text: str) -> bool:
    return any(c.isalpha() and not unicodedata.name(c, "").startswith("LATIN") for c in text)


def requested_count(text: str) -> int | None:
    """Number of items explicitly asked for ("donne-moi deux exemples d'ouverture" -> 2)."""
    match = COUNT_PATTERN.search(_fold(text))
    if not match:
        return None
    value = match.group(1)
    return NUMBERS.get(value) or int(value)
