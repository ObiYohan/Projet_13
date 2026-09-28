from pydantic import BaseModel


class TheoreticalMove(BaseModel):
    uci: str
    san: str
    white: int
    draws: int
    black: int


class EvaluationResponse(BaseModel):
    fen: str
    turn: str
    depth: int
    cp: int | None = None
    mate: int | None = None


class Opening(BaseModel):
    eco: str
    name: str


class MovesResponse(BaseModel):
    fen: str
    moves: list[TheoreticalMove] = []
    opening: Opening | None = None


class Video(BaseModel):
    video_id: str
    title: str
    channel_title: str
    published_at: str | None = None
    duration_seconds: int
    view_count: int
    like_count: int | None = None
    thumbnail_url: str | None = None
    url: str
    embed_url: str


class VideosResponse(BaseModel):
    opening: str
    query: str
    videos: list[Video] = []
    message: str | None = None


class VectorSearchResult(BaseModel):
    opening_name: str | None = None
    opening_name_fr: str | None = None
    lang: str | None = None
    eco_code: str | None = None
    moves_san: str | None = None
    source_url: str | None = None
    description_url: str | None = None
    text: str | None = None
    description: str | None = None
    score: float
    videos: list[Video] = []


class VectorSearchResponse(BaseModel):
    query: str
    lang: str
    results: list[VectorSearchResult] = []
    videos_message: str | None = None
