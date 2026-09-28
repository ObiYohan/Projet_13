import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, viewChild } from '@angular/core';
import { MoveChange, NgxChessBoardComponent, NgxChessBoardModule } from 'ngx-chess-board';

import { GameService, placement } from '../core/game.service';
import { DEMO_LINES, DemoLine } from './demo-lines';

const STATUS_LABELS = {
  check: 'Échec !',
  checkmate: 'Échec et mat',
  stalemate: 'Pat : partie nulle',
  draw: 'Partie nulle',
} as const;

@Component({
  selector: 'app-board',
  imports: [NgxChessBoardModule],
  templateUrl: './board.component.html',
  styleUrl: './board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(window:resize)': 'onResize()' },
})
export class BoardComponent {
  protected readonly game = inject(GameService);
  private readonly board = viewChild.required<NgxChessBoardComponent>('board');

  protected readonly size = signal(boardSize());
  protected readonly flipped = signal(false);
  protected readonly demoLines = DEMO_LINES;
  protected readonly demoLine = signal<DemoLine | null>(null);

  protected readonly statusLabel = computed(() => {
    const status = this.game.status();
    const turn = this.game.turn() === 'white' ? 'Blancs' : 'Noirs';
    if (status === 'checkmate') {
      return `${STATUS_LABELS.checkmate} : victoire des ${turn === 'Blancs' ? 'Noirs' : 'Blancs'}`;
    }
    return status === 'playing' ? `Trait aux ${turn}` : `${STATUS_LABELS[status]} — trait aux ${turn}`;
  });

  /** Moves grouped by move number: [{ number, white, black }]. */
  protected readonly moveRows = computed(() => {
    const rows: { number: number; white: string; black?: string }[] = [];
    this.game.moves().forEach((move, index) => {
      if (index % 2 === 0) {
        rows.push({ number: index / 2 + 1, white: move.san });
      } else {
        rows[rows.length - 1].black = move.san;
      }
    });
    return rows;
  });

  constructor() {
    // Board follows the game: new game, undo, move played from the agent panel.
    effect(() => {
      const fen = this.game.fen();
      const board = this.board();
      if (placement(board.getFEN()) !== placement(fen)) {
        board.setFEN(fen);
      }
    });
  }

  protected onResize(): void {
    this.size.set(boardSize());
  }

  protected onMoveChange(change: MoveChange): void {
    if (!this.game.applyBoardFen(change.fen)) {
      this.board().setFEN(this.game.fen());
    }
  }

  protected newGame(): void {
    this.game.reset();
    this.demoLine.set(null);
  }

  protected loadDemo(index: string): void {
    const line = this.demoLines[Number(index)];
    if (line) {
      this.game.loadLine(line.moves);
      this.demoLine.set(line);
    }
  }

  protected undo(): void {
    this.game.undo();
  }

  protected flip(): void {
    this.board().reverse();
    this.flipped.update((flipped) => !flipped);
  }
}

function boardSize(): number {
  const width = window.innerWidth;
  if (width >= 1200) {
    return 560;
  }
  if (width >= 900) {
    return 440;
  }
  return Math.max(260, Math.min(520, width - 48));
}
