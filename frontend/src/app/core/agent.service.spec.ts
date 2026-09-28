import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, TestRequest } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AgentService, ANALYSIS_DEBOUNCE_MS } from './agent.service';
import { MovesResponse, Opening, VectorSearchResponse } from './api.models';
import { GameService } from './game.service';

const E4 = { uci: 'e2e4', san: 'e4', white: 3, draws: 4, black: 3 };
const C5 = { uci: 'c7c5', san: 'c5', white: 3, draws: 4, black: 3 };
const KINGS_PAWN: Opening = { eco: 'B00', name: "King's Pawn Game" };

describe('AgentService', () => {
  let agent: AgentService;
  let game: GameService;
  let http: HttpTestingController;

  /** Lets signals propagate and the (zero) debounce elapse. */
  async function settle(): Promise<void> {
    TestBed.tick();
    await new Promise((resolve) => setTimeout(resolve, 5));
    TestBed.tick();
  }

  const movesRequests = (fen?: string) =>
    http.match((req) => req.url.startsWith('/api/v1/moves/') && (!fen || req.url.endsWith(encodeURIComponent(fen))));
  const searchRequests = () => http.match((req) => req.url === '/api/v1/vector-search');
  const evaluateRequests = () => http.match((req) => req.url.startsWith('/api/v1/evaluate/'));

  function answerMoves(request: TestRequest, moves: MovesResponse['moves'], opening: Opening | null = null): void {
    request.flush({ fen: game.fen(), moves, opening } satisfies MovesResponse);
  }

  function answerSearch(request: TestRequest): void {
    request.flush({ query: '', lang: 'fr', results: [], videos_message: null } satisfies VectorSearchResponse);
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ANALYSIS_DEBOUNCE_MS, useValue: 0 },
      ],
    });
    agent = TestBed.inject(AgentService);
    game = TestBed.inject(GameService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('analyses each position once and serves revisited positions from the cache', async () => {
    await settle();
    answerMoves(movesRequests(game.fen())[0], [E4]);

    game.playUci('e2e4');
    await settle();
    answerMoves(movesRequests()[0], [C5], KINGS_PAWN);
    await settle();
    answerSearch(searchRequests()[0]);

    game.undo();
    await settle();

    expect(movesRequests()).toHaveLength(0);
    const theory = agent.theory();
    expect(theory.fen).toBe(game.fen());
    expect(theory.state.status).toBe('success');
  });

  it('only analyses the final position of moves played in a row', async () => {
    await settle();
    movesRequests()[0].flush({ fen: game.fen(), moves: [E4], opening: null });

    game.playUci('e2e4');
    game.playUci('e7e5');
    game.playUci('g1f3');
    await settle();

    const requests = movesRequests();
    expect(requests).toHaveLength(1);
    expect(requests[0].request.url).toContain(encodeURIComponent(game.fen()));
    answerMoves(requests[0], []);
    await settle();
    evaluateRequests().forEach((request) => request.flush({}));
  });

  it('keeps the last named opening and only searches its context once', async () => {
    await settle();
    answerMoves(movesRequests()[0], [E4]);

    game.playUci('e2e4');
    await settle();
    answerMoves(movesRequests()[0], [C5], KINGS_PAWN);
    await settle();
    const search = searchRequests();
    expect(search).toHaveLength(1);
    expect(search[0].request.params.get('eco')).toBe('B00');
    answerSearch(search[0]);

    game.playUci('c7c5');
    await settle();
    answerMoves(movesRequests()[0], [], null);
    await settle();
    evaluateRequests().forEach((request) => request.flush({}));

    expect(agent.currentOpening()).toEqual({ ...KINGS_PAWN, current: false });
    expect(searchRequests()).toHaveLength(0);
  });

  it('asks Stockfish only once the game is out of theory', async () => {
    await settle();
    answerMoves(movesRequests()[0], [E4]);
    await settle();
    expect(evaluateRequests()).toHaveLength(0);

    game.playUci('a2a3');
    await settle();
    answerMoves(movesRequests()[0], []);
    await settle();

    const evaluation = evaluateRequests();
    expect(evaluation).toHaveLength(1);
    evaluation[0].flush({ fen: game.fen(), turn: 'black', depth: 15, cp: -20, mate: null });
    await settle();
    expect(agent.evaluation().state.status).toBe('success');
  });

  it('reports a network error and retries on demand', async () => {
    await settle();
    movesRequests()[0].error(new ProgressEvent('error'));
    await settle();

    const failed = agent.theory().state;
    expect(failed.status).toBe('error');
    expect(failed.status === 'error' && failed.error).toContain("Impossible de joindre l'API");

    agent.retryTheory();
    await settle();
    answerMoves(movesRequests()[0], [E4]);
    await settle();

    expect(agent.theory().state.status).toBe('success');
  });
});
