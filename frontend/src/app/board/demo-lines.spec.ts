import { Chess } from 'chess.js';

import { DEMO_LINES } from './demo-lines';

describe('DEMO_LINES', () => {
  it.each(DEMO_LINES.map((line) => [line.name, line.moves] as const))('%s is a legal line', (_, moves) => {
    const chess = new Chess();
    for (const move of moves) {
      expect(() => chess.move(move)).not.toThrow();
    }
  });
});
