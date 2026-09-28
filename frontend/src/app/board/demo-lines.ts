/** Positions prepared for the client demonstration: each shows one side of the agent. */
export interface DemoLine {
  name: string;
  description: string;
  /** Moves in standard algebraic notation (English piece letters). */
  moves: string[];
}

export const DEMO_LINES: DemoLine[] = [
  {
    name: 'Sicilienne, variante Najdorf',
    description:
      "L'ouverture la plus étudiée : théorie très riche, fiche du corpus et vidéos dédiées.",
    moves: ['e4', 'c5', 'Nf3', 'd6', 'd4', 'cxd4', 'Nxd4', 'Nf6', 'Nc3', 'a6'],
  },
  {
    name: 'Partie espagnole, défense berlinoise',
    description: 'Le « mur de Berlin » popularisé par Kramnik : fiche exacte de la variante.',
    moves: ['e4', 'e5', 'Nf3', 'Nc6', 'Bb5', 'Nf6'],
  },
  {
    name: 'Gambit Evans',
    description: 'Les Blancs sacrifient un pion pour gagner du temps : contexte historique et plans.',
    moves: ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'Bc5', 'b4'],
  },
  {
    name: "Défense française, variante d'avance",
    description: 'Structure de pions bloquée : fiche tirée de la section de l’article.',
    moves: ['e4', 'e6', 'd4', 'd5', 'e5'],
  },
  {
    name: 'Gambit dame refusé',
    description: 'Un classique des débuts fermés avec 1.d4.',
    moves: ['d4', 'd5', 'c4', 'e6'],
  },
  {
    name: 'Défense est-indienne, variante normale',
    description:
      "Code E70 absent du corpus : l'agent propose la fiche la plus proche (défense est-indienne).",
    moves: ['d4', 'Nf6', 'c4', 'g6', 'Nc3', 'Bg7', 'e4', 'd6'],
  },
  {
    name: 'Piège du berger',
    description:
      'Après 3...Nf6?? la partie sort de la théorie : Stockfish prend le relais et trouve le mat en un coup.',
    moves: ['e4', 'e5', 'Qh5', 'Nc6', 'Bc4', 'Nf6'],
  },
];
