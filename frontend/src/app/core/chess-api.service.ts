import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable, InjectionToken } from '@angular/core';
import { Observable, timeout } from 'rxjs';

import { EvaluationResponse, Lang, MovesResponse, VectorSearchResponse } from './api.models';

/** Base URL of the backend: relative, served by the dev proxy or nginx. */
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  factory: () => '/api/v1',
});

const REQUEST_TIMEOUT_MS = 30_000;
// The first semantic search may include YouTube searches: allow it more time.
const SEARCH_TIMEOUT_MS = 60_000;

/** HTTP calls to the chess agent backend. */
@Injectable({ providedIn: 'root' })
export class ChessApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  /** Theoretical moves (Lichess masters) and named opening of a position. */
  getMoves(fen: string): Observable<MovesResponse> {
    return this.http
      .get<MovesResponse>(`${this.baseUrl}/moves/${encodeURIComponent(fen)}`)
      .pipe(timeout(REQUEST_TIMEOUT_MS));
  }

  /** Stockfish evaluation of a position. */
  evaluate(fen: string): Observable<EvaluationResponse> {
    return this.http
      .get<EvaluationResponse>(`${this.baseUrl}/evaluate/${encodeURIComponent(fen)}`)
      .pipe(timeout(REQUEST_TIMEOUT_MS));
  }

  /**
   * Context (Milvus) and videos (YouTube) about an opening, in `lang`: the
   * opening of code `eco` if the corpus has it, else the closest one to `query`.
   */
  searchOpening(query: string, lang: Lang, eco?: string, topK = 1): Observable<VectorSearchResponse> {
    let params = new HttpParams().set('query', query).set('lang', lang).set('top_k', topK);
    if (eco) {
      params = params.set('eco', eco);
    }
    return this.http
      .get<VectorSearchResponse>(`${this.baseUrl}/vector-search`, { params })
      .pipe(timeout(SEARCH_TIMEOUT_MS));
  }
}
