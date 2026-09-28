import { ChangeDetectionStrategy, Component } from '@angular/core';

import { AgentPanelComponent } from './agent-panel/agent-panel.component';
import { BoardComponent } from './board/board.component';

@Component({
  selector: 'app-root',
  imports: [BoardComponent, AgentPanelComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {}
