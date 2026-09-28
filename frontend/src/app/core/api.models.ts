/** Response types of the FastAPI backend (see backend/api/schemas.py). */

export type Lang = 'fr' | 'en';

export interface Opening {
  eco: string;
  name: string;
}

export interface TheoreticalMove {
  uci: string;
  san: string;
  white: number;
  draws: number;
  black: number;
}

export interface MovesResponse {
  fen: string;
  moves: TheoreticalMove[];
  opening: Opening | null;
}

export interface EvaluationResponse {
  fen: string;
  turn: 'white' | 'black';
  depth: number;
  cp: number | null;
  mate: number | null;
}

export interface Video {
  video_id: string;
  title: string;
  channel_title: string;
  published_at: string | null;
  duration_seconds: number;
  view_count: number;
  like_count: number | null;
  thumbnail_url: string | null;
  url: string;
  embed_url: string;
}

export interface VectorSearchResult {
  opening_name: string | null;
  opening_name_fr: string | null;
  lang: Lang | null;
  eco_code: string | null;
  moves_san: string | null;
  source_url: string | null;
  description_url: string | null;
  /** Best-matching passage, starting with a header (names, ECO code, moves). */
  text: string | null;
  /** The opening's passages found in that passage's language, without headers. */
  description: string | null;
  score: number;
  videos: Video[];
}

export interface VectorSearchResponse {
  query: string;
  lang: Lang;
  results: VectorSearchResult[];
  videos_message: string | null;
}
