import { computed, Injectable, signal } from '@angular/core';
import { Chess, Move } from 'chess.js';

export type GameStatus = 'playing' | 'check' | 'checkmate' | 'stalemate' | 'draw';

interface GameState {
  fen: string;
  /** Positions of the game, from the initial one to the current one. */
  positions: string[];
  moves: Move[];
  status: GameStatus;
}

/** Piece placement field of a FEN: identifies a position on the board. */
export function placement(fen: string): string {
  return fen.split(' ')[0];
}

/**
 * Single source of truth of the game, backed by chess.js. The chessboard only
 * displays this state and reports the positions reached by the player.
 */
@Injectable({ providedIn: 'root' })
export class GameService {
  private readonly chess = new Chess();
  private readonly state = signal<GameState>(this.snapshot());

  readonly fen = computed(() => this.state().fen);
  readonly positions = computed(() => this.state().positions);
  readonly moves = computed(() => this.state().moves);
  readonly status = computed(() => this.state().status);
  readonly turn = computed<'white' | 'black'>(() =>
    this.state().fen.split(' ')[1] === 'w' ? 'white' : 'black',
  );
  readonly isGameOver = computed(() => ['checkmate', 'stalemate', 'draw'].includes(this.status()));

  /**
   * Applies the legal move leading to `boardFen` (the position shown by the
   * chessboard after a drag), promotions included. Returns false if none does.
   */
  applyBoardFen(boardFen: string): boolean {
    const target = placement(boardFen);
    if (target === placement(this.chess.fen())) {
      return true;
    }
    const move = this.chess.moves({ verbose: true }).find((m) => placement(m.after) === target);
    if (!move) {
      return false;
    }
    this.chess.move(move);
    this.update();
    return true;
  }

  /** Plays a move in UCI notation ("e2e4", "e7e8q"). Returns false if illegal. */
  playUci(uci: string): boolean {
    try {
      this.chess.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] });
    } catch {
      return false;
    }
    this.update();
    return true;
  }

  /** Starts a new game and plays `moves` (SAN), e.g. a demonstration line. */
  loadLine(moves: string[]): void {
    this.chess.reset();
    for (const move of moves) {
      this.chess.move(move);
    }
    this.update();
  }

  undo(): void {
    if (this.chess.undo()) {
      this.update();
    }
  }

  reset(): void {
    this.chess.reset();
    this.update();
  }

  private update(): void {
    this.state.set(this.snapshot());
  }

  private snapshot(): GameState {
    const moves = this.chess.history({ verbose: true });
    const initial = moves.length ? moves[0].before : this.chess.fen();
    return {
      fen: this.chess.fen(),
      positions: [initial, ...moves.map((m) => m.after)],
      moves,
      status: this.chess.isCheckmate()
        ? 'checkmate'
        : this.chess.isStalemate()
          ? 'stalemate'
          : this.chess.isDraw()
            ? 'draw'
            : this.chess.isCheck()
              ? 'check'
              : 'playing',
    };
  }
}
