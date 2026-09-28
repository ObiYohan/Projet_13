# Interface Angular — Coach d'ouvertures

Application Angular 22 : un échiquier interactif ([ngx-chess-board](https://github.com/grzegorz103/ngx-chess-board)) et un panneau de recommandations de l'agent (ouverture, coups théoriques, évaluation Stockfish, contexte, vidéos).

## Lancer en développement

Le backend doit tourner (`docker compose up -d` à la racine du dépôt). Puis :

```bash
npm install
npm start            # http://localhost:4200, les appels /api sont redirigés vers http://localhost:8000 (proxy.conf.json)
npm test             # tests unitaires (Vitest)
npm run build        # build de production dans dist/chess-agent/browser
```

Avec Docker Compose, l'application est servie par nginx sur http://localhost:4200 ; nginx redirige `/api/` vers le conteneur `api` (même origine : pas de CORS).

## Organisation

```
src/app/
  core/
    api.models.ts          types des réponses du backend
    chess-api.service.ts   appels HTTP (/moves, /evaluate, /vector-search) avec délai maximal
    remote-data.ts         état chargement / succès / erreur et messages d'erreur réseau
    game.service.ts        état de la partie (chess.js) : source de vérité unique
    agent.service.ts       orchestration des recommandations pour la position courante
  board/                   échiquier, contrôles, liste des coups
  agent-panel/             panneau de l'agent et liste de vidéos (lecteur intégré)
```

## Fonctionnement

**Synchronisation échiquier ↔ agent**
- `GameService` (chess.js) détient la partie. L'échiquier ne fait qu'afficher : après un coup joué à la souris, le service retrouve le coup légal menant à la position affichée (promotions et roques compris). Nouvelle partie, annulation et coups joués depuis le panneau passent par le service, et l'échiquier se recale sur sa position.
- Chaque résultat de l'agent est étiqueté avec la position (FEN) pour laquelle il a été demandé : le panneau n'affiche jamais les coups ou l'évaluation d'une autre position.

**Recommandations pour une position**
1. `/moves/{fen}` : coups théoriques (parties de maîtres Lichess) et ouverture nommée.
2. Hors théorie (aucun coup) : `/evaluate/{fen}` (Stockfish). Sinon, l'évaluation reste disponible à la demande.
3. Quand l'ouverture change : `/vector-search?query=<nom>&eco=<code>&lang=<fr|en>&top_k=1` renvoie en un appel la fiche de l'ouverture et ses vidéos. Si la position n'est pas nommée, la dernière ouverture reconnue de la partie est conservée.

**Appels API évités**
- Anti-rebond de 300 ms : les positions traversées rapidement ne sont pas analysées.
- Cache par position (coups, évaluation) et par ouverture + langue (contexte, vidéos) : revenir en arrière ne relance aucun appel.
- Les requêtes devenues obsolètes (position changée entre-temps) sont annulées.
- Stockfish n'est appelé qu'hors théorie ou à la demande ; contexte et vidéos seulement quand l'ouverture change.

**Chargement et erreurs** : chaque section a son propre indicateur de chargement et son message d'erreur (API injoignable, trop de requêtes, délai dépassé, erreur serveur) avec un bouton « Réessayer ».

## Dépendances à connaître

- **ngx-chess-board 2.2.3** : dernière version compilée publiée sur npm (la 3.0.0 ne contient que les sources). Elle cible Angular 13 : `overrides` dans `package.json` lui impose les versions d'Angular du projet, et l'application garde la détection de changements par zone.js. Elle utilise `lodash` sans le déclarer : il est ajouté aux dépendances.
- **chess.js** : règles du jeu (coups légaux, SAN, FEN, mat, pat).
