import { TestBed } from '@angular/core/testing';
import { Chess } from 'chess.js';

import { GameService } from './game.service';

/** Position the board would show after playing `move` in `fen`. */
function after(fen: string, move: { from: string; to: string; promotion?: string }): string {
  const chess = new Chess(fen);
  chess.move(move);
  return chess.fen();
}

describe('GameService', () => {
  let game: GameService;

  beforeEach(() => {
    game = TestBed.inject(GameService);
  });

  it('finds the move leading to the position shown by the board', () => {
    expect(game.applyBoardFen(after(game.fen(), { from: 'e2', to: 'e4' }))).toBe(true);

    expect(game.moves().map((m) => m.san)).toEqual(['e4']);
    expect(game.turn()).toBe('black');
    expect(game.positions()).toHaveLength(2);
  });

  it('rejects a position that no legal move leads to', () => {
    const twoMoves = 'rnbqkbnr/pppppppp/8/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 1';

    expect(game.applyBoardFen(twoMoves)).toBe(false);
    expect(game.moves()).toHaveLength(0);
  });

  it('recognises the piece chosen for a promotion', () => {
    for (const uci of ['a2a4', 'b7b5', 'a4b5', 'a7a6', 'b5a6', 'c8b7', 'a6b7', 'b8c6']) {
      expect(game.playUci(uci)).toBe(true);
    }

    game.applyBoardFen(after(game.fen(), { from: 'b7', to: 'a8', promotion: 'n' }));

    expect(game.moves().at(-1)?.san).toBe('bxa8=N');
  });

  it('recognises castling', () => {
    for (const uci of ['e2e4', 'e7e5', 'g1f3', 'b8c6', 'f1c4', 'f8c5']) {
      game.playUci(uci);
    }

    game.applyBoardFen(after(game.fen(), { from: 'e1', to: 'g1' }));

    expect(game.moves().at(-1)?.san).toBe('O-O');
  });

  it('detects checkmate', () => {
    for (const uci of ['f2f3', 'e7e5', 'g2g4', 'd8h4']) {
      game.playUci(uci);
    }

    expect(game.status()).toBe('checkmate');
    expect(game.isGameOver()).toBe(true);
  });

  it('undoes and resets', () => {
    game.playUci('e2e4');
    game.playUci('e7e5');

    game.undo();
    expect(game.moves().map((m) => m.san)).toEqual(['e4']);

    game.reset();
    expect(game.moves()).toHaveLength(0);
    expect(game.positions()).toEqual([game.fen()]);
  });

  it('loads a line of moves from a new game', () => {
    game.playUci('d2d4');

    game.loadLine(['e4', 'c5', 'Nf3']);

    expect(game.moves().map((m) => m.san)).toEqual(['e4', 'c5', 'Nf3']);
    expect(game.positions()).toHaveLength(4);
  });

  it('refuses an illegal move', () => {
    expect(game.playUci('e2e5')).toBe(false);
    expect(game.moves()).toHaveLength(0);
  });
});
