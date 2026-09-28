import { computed, inject, Injectable, InjectionToken, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import {
  catchError,
  debounceTime,
  distinctUntilChanged,
  map,
  merge,
  Observable,
  of,
  share,
  shareReplay,
  startWith,
  Subject,
  switchMap,
  tap,
} from 'rxjs';

import {
  EvaluationResponse,
  Lang,
  MovesResponse,
  Opening,
  VectorSearchResult,
} from './api.models';
import { ChessApiService } from './chess-api.service';
import { GameService } from './game.service';
import { failure, IDLE, LOADING, RemoteData, success } from './remote-data';

/** Delay before analysing a position: positions played through quickly aren't sent. */
export const ANALYSIS_DEBOUNCE_MS = new InjectionToken<number>('ANALYSIS_DEBOUNCE_MS', {
  factory: () => 300,
});

/** Data about one position, tagged with that position so the UI never shows it for another. */
export interface PositionData<T> {
  fen: string;
  state: RemoteData<T>;
}

export interface CurrentOpening extends Opening {
  /** False when the current position isn't named: this is the last named one of the game. */
  current: boolean;
}

export interface OpeningContext {
  /** Closest passage of the openings corpus, with its videos (null if none). */
  result: VectorSearchResult | null;
  videosMessage: string | null;
}

/**
 * Orchestrates the agent's recommendations for the position on the board:
 * theoretical moves and opening (Lichess), then either context and videos
 * (Milvus + YouTube) or, out of theory, a Stockfish evaluation.
 */
@Injectable({ providedIn: 'root' })
export class AgentService {
  private readonly api = inject(ChessApiService);
  private readonly game = inject(GameService);
  private readonly debounceMs = inject(ANALYSIS_DEBOUNCE_MS);

  /** Language of the context and videos. */
  readonly lang = signal<Lang>('fr');

  private readonly movesCache = new Map<string, Observable<MovesResponse>>();
  private readonly evaluationCache = new Map<string, Observable<EvaluationResponse>>();
  private readonly contextCache = new Map<string, Observable<OpeningContext>>();

  private readonly retryTheory$ = new Subject<void>();
  private readonly evaluationRequests$ = new Subject<string>();
  private readonly retryContext$ = new Subject<void>();

  /** Opening named by Lichess for each analysed position (null: not named). */
  private readonly openingsByFen = signal<ReadonlyMap<string, Opening | null>>(new Map());

  private readonly analysedFen$ = toObservable(this.game.fen).pipe(
    debounceTime(this.debounceMs),
    distinctUntilChanged(),
  );

  private readonly theory$: Observable<PositionData<MovesResponse>> = merge(
    this.analysedFen$,
    this.retryTheory$.pipe(map(() => this.game.fen())),
  ).pipe(
    switchMap((fen) =>
      this.game.isGameOver()
        ? of({ fen, state: IDLE })
        : this.cached(this.movesCache, fen, () => this.api.getMoves(fen)).pipe(
            tap((response) => this.rememberOpening(fen, response.opening)),
            map((response) => ({ fen, state: success(response) })),
            catchError((error) => of({ fen, state: failure<MovesResponse>(error) })),
            startWith({ fen, state: LOADING }),
          ),
    ),
    share(),
  );

  readonly theory = toSignal(this.theory$, {
    initialValue: { fen: this.game.fen(), state: IDLE } as PositionData<MovesResponse>,
  });

  /** Stockfish runs automatically out of theory, or on request. */
  readonly evaluation = toSignal(
    merge(
      this.theory$.pipe(
        map(({ fen, state }) => ({
          fen,
          run: state.status === 'success' && state.data.moves.length === 0,
        })),
      ),
      this.evaluationRequests$.pipe(map((fen) => ({ fen, run: true }))),
    ).pipe(
      switchMap(({ fen, run }) =>
        !run
          ? of({ fen, state: IDLE })
          : this.cached(this.evaluationCache, fen, () => this.api.evaluate(fen)).pipe(
              map((response) => ({ fen, state: success(response) })),
              catchError((error) => of({ fen, state: failure<EvaluationResponse>(error) })),
              startWith({ fen, state: LOADING }),
            ),
      ),
    ),
    { initialValue: { fen: this.game.fen(), state: IDLE } as PositionData<EvaluationResponse> },
  );

  /** Current opening, or the last named one reached in the game. */
  readonly currentOpening = computed<CurrentOpening | null>(() => {
    const known = this.openingsByFen();
    const positions = this.game.positions();
    for (let i = positions.length - 1; i >= 0; i--) {
      const opening = known.get(positions[i]);
      if (opening) {
        return { ...opening, current: i === positions.length - 1 };
      }
    }
    return null;
  });

  private readonly contextKey = computed(
    () => {
      const opening = this.currentOpening();
      return opening ? { name: opening.name, eco: opening.eco, lang: this.lang() } : null;
    },
    { equal: (a, b) => a?.name === b?.name && a?.eco === b?.eco && a?.lang === b?.lang },
  );

  /** Context and videos: reloaded only when the opening or the language changes. */
  readonly context = toSignal(
    merge(
      toObservable(this.contextKey),
      this.retryContext$.pipe(map(() => this.contextKey())),
    ).pipe(
      switchMap((key) =>
        !key
          ? of(IDLE)
          : this.cached(this.contextCache, `${key.lang}|${key.eco}|${key.name}`, () =>
              this.api.searchOpening(key.name, key.lang, key.eco).pipe(
                map((response) => ({
                  result: response.results[0] ?? null,
                  videosMessage: response.videos_message,
                })),
              ),
            ).pipe(
              map((context) => success(context)),
              catchError((error) => of(failure<OpeningContext>(error))),
              startWith(LOADING),
            ),
      ),
    ),
    { initialValue: IDLE as RemoteData<OpeningContext> },
  );

  retryTheory(): void {
    this.retryTheory$.next();
  }

  requestEvaluation(): void {
    this.evaluationRequests$.next(this.game.fen());
  }

  retryContext(): void {
    this.retryContext$.next();
  }

  private rememberOpening(fen: string, opening: Opening | null): void {
    this.openingsByFen.update((known) => new Map(known).set(fen, opening));
  }

  /**
   * One shared request per key: replayed once completed, retried after an
   * error, and cancelled when nobody listens anymore (obsolete position).
   */
  private cached<T>(
    cache: Map<string, Observable<T>>,
    key: string,
    load: () => Observable<T>,
  ): Observable<T> {
    let request = cache.get(key);
    if (!request) {
      request = load().pipe(shareReplay({ bufferSize: 1, refCount: true }));
      cache.set(key, request);
    }
    return request;
  }
}
