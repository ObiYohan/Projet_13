import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { AgentService, PositionData } from '../core/agent.service';
import { Lang } from '../core/api.models';
import { GameService } from '../core/game.service';
import { IDLE, LOADING, RemoteData } from '../core/remote-data';
import { VideoListComponent } from './video-list.component';

const numbers = new Intl.NumberFormat('fr-FR');

@Component({
  selector: 'app-agent-panel',
  imports: [VideoListComponent],
  templateUrl: './agent-panel.component.html',
  styleUrl: './agent-panel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AgentPanelComponent {
  protected readonly agent = inject(AgentService);
  protected readonly game = inject(GameService);

  protected readonly positionLabel = computed(() => {
    const moves = this.game.moves();
    if (!moves.length) {
      return 'Position de départ';
    }
    const last = moves[moves.length - 1];
    return `Position après ${Math.ceil(moves.length / 2)}${last.color === 'w' ? '.' : '...'} ${last.san}`;
  });

  // Results only count for the position on the board: while the new position
  // is being analysed, the previous one's results are hidden.
  protected readonly theory = computed(() => this.forBoard(this.agent.theory(), LOADING));
  protected readonly evaluation = computed(() => this.forBoard(this.agent.evaluation(), IDLE));

  protected readonly theoryMoves = computed(() => {
    const theory = this.theory();
    if (theory.status !== 'success') {
      return [];
    }
    return theory.data.moves.map((move) => {
      const games = move.white + move.draws + move.black;
      const pct = (n: number) => (games ? Math.round((100 * n) / games) : 0);
      return {
        ...move,
        games: numbers.format(games),
        white: pct(move.white),
        draws: pct(move.draws),
        black: pct(move.black),
      };
    });
  });

  protected readonly outOfTheory = computed(() => {
    const theory = this.theory();
    return theory.status === 'success' && theory.data.moves.length === 0;
  });

  protected readonly evaluationView = computed(() => {
    const evaluation = this.evaluation();
    if (evaluation.status !== 'success') {
      return null;
    }
    const { cp, mate, depth } = evaluation.data;
    if (mate !== null) {
      return {
        score: `M${Math.abs(mate)}`,
        verdict: `Mat en ${Math.abs(mate)} pour les ${mate > 0 ? 'Blancs' : 'Noirs'}`,
        whiteShare: mate > 0 ? 100 : 0,
        depth,
      };
    }
    const pawns = (cp ?? 0) / 100;
    const side = pawns > 0 ? 'Blancs' : 'Noirs';
    const gap = Math.abs(pawns);
    return {
      score: `${pawns > 0 ? '+' : ''}${pawns.toFixed(2).replace('.', ',')}`,
      verdict:
        gap < 0.3
          ? 'Position équilibrée'
          : gap < 1
            ? `Léger avantage aux ${side}`
            : gap < 3
              ? `Net avantage aux ${side}`
              : `Avantage décisif aux ${side}`,
      // Winning chances curve used by Lichess.
      whiteShare: Math.round(50 + 50 * (2 / (1 + Math.exp(-0.00368 * (cp ?? 0))) - 1)),
      depth,
    };
  });

  protected readonly contextView = computed(() => {
    const context = this.agent.context();
    if (context.status !== 'success' || !context.data.result) {
      return null;
    }
    const result = context.data.result;
    const french = this.agent.lang() === 'fr';
    return {
      name: (french && result.opening_name_fr) || result.opening_name,
      eco: result.eco_code,
      moves: result.moves_san,
      paragraphs: (result.description ?? '').split('\n\n').filter((p) => p.trim()),
      sourceUrl: result.description_url,
      closestMatch: result.eco_code !== this.agent.currentOpening()?.eco,
      videos: result.videos,
      videosMessage: context.data.videosMessage,
    };
  });

  /** Opening name: the corpus' French name when its entry is this very opening. */
  protected readonly openingTitle = computed(() => {
    const opening = this.agent.currentOpening();
    if (!opening) {
      return null;
    }
    const context = this.contextView();
    const localName = context && !context.closestMatch ? context.name : null;
    return localName && localName !== opening.name
      ? { name: localName, alias: opening.name }
      : { name: opening.name, alias: null };
  });

  protected playMove(uci: string): void {
    this.game.playUci(uci);
  }

  protected setLang(lang: Lang): void {
    this.agent.lang.set(lang);
  }

  private forBoard<T>(data: PositionData<T>, otherwise: RemoteData<T>): RemoteData<T> {
    return data.fen === this.game.fen() ? data.state : otherwise;
  }
}
