# Coach d'ouvertures — Agent IA d'apprentissage des ouvertures d'échecs

Agent intelligent qui accompagne les jeunes joueurs dans l'apprentissage des ouvertures. À chaque coup joué sur l'échiquier, il propose :

- les **meilleurs coups de la théorie** (parties de maîtres, Lichess) ;
- le **contexte de l'ouverture** (fiches Wikipédia indexées dans Milvus, en français ou en anglais) ;
- des **vidéos explicatives** YouTube, lisibles dans la page ;
- une **évaluation Stockfish** dès que la partie évolue.

## Démarrage rapide

```bash
git clone <url-du-dépôt> && cd Projet_13
cp .env.example .env          # puis renseigner LICHESS_API_TOKEN et API_KEY_YOUTUBE
docker compose up -d --build  # premier démarrage : ~10 min (build, modèle, corpus)
```

Ouvrir **http://localhost:4200**.

## Installation pas à pas

### 1. Prérequis

| Élément | Détail |
|---|---|
| Docker Desktop (ou Docker Engine + Compose v2) | Docker 25 ou plus récent (healthchecks `start_interval`) |
| Ressources allouées à Docker | 4 CPU et 6 Go de RAM minimum (8 CPU / 8 Go conseillés), ~10 Go de disque |
| Token Lichess | https://lichess.org/account/oauth/token → « Nouveau token », aucun scope à cocher |
| Clé YouTube Data API v3 | Google Cloud Console → activer « YouTube Data API v3 » → Identifiants → Créer une clé API |
| Accès Internet | Lichess, YouTube, Hugging Face (modèle), PyPI / npm (build) |
| Ports libres | 4200 (interface) et 8000 (API), modifiables dans `.env` |

### 2. Configuration

```bash
cp .env.example .env
```

Renseigner dans `.env` :

```env
LICHESS_API_TOKEN=lip_xxxxxxxxxxxx
API_KEY_YOUTUBE=AIzaxxxxxxxxxxxxxxxx
```

Les autres variables ont des valeurs par défaut (voir les commentaires de [.env.example](.env.example)). Le fichier `.env` est ignoré par git : les clés ne sont jamais versionnées.

### 3. Démarrage

```bash
docker compose up -d --build
```

Ordre de démarrage :

```
etcd, minio ─▶ standalone (Milvus) ─▶ openings-loader ─▶ api ─▶ frontend
```

### 4. Vérification

```bash
docker compose ps
```

Tous les services doivent être `Up (healthy)`, et les deux services d'initialisation `Exited (0)` :

```
SERVICE              STATUS
api                  Up (healthy)
etcd                 Up (healthy)
frontend             Up (healthy)
milvus-volume-init   Exited (0)
minio                Up (healthy)
openings-loader      Exited (0)
standalone           Up (healthy)
```

```bash
curl http://localhost:8000/api/v1/healthcheck   # {"status":"ok"}
docker compose logs openings-loader              # "Loaded 70 opening(s) as 268 chunk(s)…" ou "…nothing to do."
```

Puis ouvrir **http://localhost:4200** (interface) et **http://localhost:8000/docs** (documentation Swagger de l'API).

## Démonstration

### Positions préparées

Le menu **« Positions de démonstration »** (sous l'échiquier) joue une séquence de coups en un clic. Les coups sont notés en notation anglaise, comme dans l'interface (N = cavalier, B = fou, Q = dame). Chaque position met en avant une facette de l'agent :

| Position | Coups | Ce qu'elle montre |
|---|---|---|
| Sicilienne, variante Najdorf | 1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6 | L'ouverture la plus étudiée : 12 coups théoriques, fiche B90, vidéos en français |
| Partie espagnole, défense berlinoise | 1.e4 e5 2.Nf3 Nc6 3.Bb5 Nf6 | Fiche exacte d'une variante (C65), le « mur de Berlin » de Kramnik |
| Gambit Evans | 1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.b4 | Un gambit : sacrifice de pion, contexte historique (C51) |
| Défense française, variante d'avance | 1.e4 e6 2.d4 d5 3.e5 | Fiche tirée d'une section d'article (C02) |
| Gambit dame refusé | 1.d4 d5 2.c4 e6 | Débuts fermés avec 1.d4 (D30) |
| Défense est-indienne, variante normale | 1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 | Code E70 absent du corpus : l'agent propose la **fiche la plus proche** (E60) et le signale |
| Piège du berger | 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6?? | **Hors théorie** : Stockfish prend le relais et annonce **« Mat en 1 pour les Blancs »** (4.Qxf7#) |

### Déroulé proposé (~10 min)

1. **Jouer 1.e4 à la souris** : l'agent reconnaît l'« Ouverture du pion roi » (B00) et liste les réponses des maîtres avec leurs résultats.
2. **Cliquer sur « c5 »** dans le panneau : le coup est joué sur l'échiquier, la « Défense sicilienne » est identifiée, sa fiche et trois vidéos en français s'affichent.
3. **Lancer une vidéo** : lecture intégrée à la page ; « Ouvrir sur YouTube » pour la voir en plein écran.
4. **Choisir « Sicilienne, variante Najdorf »** : théorie profonde ; cliquer quelques coups proposés pour suivre la ligne principale.
5. **Choisir « Défense est-indienne »** : montrer la fiche la plus proche quand le corpus n'a pas l'ouverture exacte.
6. **Choisir « Piège du berger »** : sortie de théorie, évaluation Stockfish et mat en 1 ; jouer 4.Qxf7# (dame de h5 en f7) pour « Échec et mat ».
7. **Passer en EN** : contexte et vidéos basculent en anglais.
8. **« Annuler le coup »** et **« Retourner l'échiquier »** : l'agent suit la position sans nouvel appel (cache).


## Services Docker

| Service | Image | Rôle | Port hôte | Volume | Healthcheck |
|---|---|---|---|---|---|
| `frontend` | build `frontend/` (nginx) | Interface Angular, proxy `/api/` vers `api` | 4200 | — | page d'accueil |
| `api` | build `backend/` (`chess-agent-api`) | FastAPI + LangGraph, Stockfish, Lichess, YouTube | 8000 | `hf_cache`, `./data` (lecture) | `/api/v1/healthcheck` |
| `openings-loader` | `chess-agent-api` | Au démarrage : charge `data/openings.json` dans Milvus si la collection est vide, puis s'arrête | — | `hf_cache`, `./data` (lecture) | code de sortie 0 |
| `standalone` | `milvusdb/milvus:v3.0.2` | Base vectorielle Milvus | — | `milvus_data` | `/healthz` |
| `etcd` | `quay.io/coreos/etcd:v3.5.25` | Métadonnées de Milvus | — | `etcd_data` | `etcdctl endpoint health` |
| `minio` | `quay.io/minio/minio` | Stockage objet de Milvus | — | `minio_data` | `mc ready local` |
| `milvus-volume-init` | `milvusdb/milvus:v3.0.2` | Au démarrage : donne le volume `milvus_data` à l'utilisateur de Milvus | — | `milvus_data` | code de sortie 0 |


## Données persistantes

| Volume | Contenu | Taille |
|---|---|---|
| `projet_13_milvus_data` | Données et journal de Milvus | ~2 Mo |
| `projet_13_etcd_data` | Métadonnées de Milvus (collections, segments) | ~150 Mo |
| `projet_13_minio_data` | Fichiers des segments Milvus | < 1 Mo à ~20 Mo |
| `projet_13_hf_cache` | Modèle d'embedding Qwen3-Embedding-0.6B | ~1,2 Go |

Le préfixe `projet_13_` est le nom du projet Compose (nom du dossier). Les volumes sont déclarés dans la section `volumes:` de [docker-compose.yml](docker-compose.yml).

```bash
docker volume ls --filter name=projet_13          # lister les volumes du projet
docker volume inspect projet_13_milvus_data       # emplacement, pilote, labels Compose
docker system df -v                               # taille de chaque volume
```

**Vérifier la persistance** (le corpus et le modèle doivent survivre à la suppression des conteneurs) :

```bash
docker compose down                   # supprime les conteneurs, conserve les volumes
docker compose up -d
docker compose logs openings-loader   # "…already holds 268 chunk(s): nothing to do."
```

Testé : après `docker compose down` puis `up -d`, la stack redémarre en ~30 s, sans nouveau téléchargement du modèle ni rechargement du corpus.

**Repartir de zéro** (supprime aussi le corpus Milvus et le modèle, qui seront recréés au démarrage suivant) :

```bash
docker compose down -v
```

> Les versions précédentes stockaient Milvus dans un dossier `volumes/` du projet. Il n'est plus utilisé et peut être supprimé.

## Commandes utiles

```bash
docker compose ps                                  # état des services
docker compose logs -f api                         # journaux de l'API (ou frontend, openings-loader, standalone…)
docker compose restart api                         # redémarrer un service
docker compose up -d --build api frontend          # reconstruire après une modification du code
docker compose exec api python -m api.scripts.load_openings   # recharger le corpus après modification de data/openings.json
docker compose stop                                # arrêter sans rien supprimer
docker compose down                                # supprimer les conteneurs (volumes conservés)
```


## Interface

- **Échiquier interactif** ([ngx-chess-board](https://github.com/grzegorz103/ngx-chess-board)) : coups à la souris (glisser ou cliquer), nouvelle partie, annulation, retournement, liste des coups joués, positions de démonstration.
- **Panneau de l'agent**, mis à jour à chaque coup :
  - **Ouverture** jouée (code ECO, nom français et nom Lichess), ou la dernière reconnue ;
  - **Coups théoriques** des parties de maîtres avec leurs résultats (Blancs / nulles / Noirs) — un clic sur un coup le joue ;
  - **Évaluation Stockfish**, automatique dès que la partie sort de la théorie, ou à la demande ;
  - **Contexte** de l'ouverture (fiche Wikipédia du corpus Milvus) ;
  - **Vidéos** explicatives (jusqu'à 3), lisibles directement dans la page.
- Contexte et vidéos en **français ou en anglais** (bouton FR / EN).

Détails de fonctionnement (synchronisation, appels API évités, gestion des erreurs) : [frontend/README.md](frontend/README.md).

## Fonctionnalités de l'API

| Fonctionnalité | Endpoint | Source |
|---|---|---|
| Coups théoriques et ouverture d'une position | `GET /api/v1/moves/{fen}` | API Lichess (base *masters*) |
| Évaluation d'une position | `GET /api/v1/evaluate/{fen}` | Stockfish (profondeur 15) |
| Recherche sémantique sur les ouvertures, avec vidéos suggérées | `GET /api/v1/vector-search?query=...` | Milvus + LangGraph |
| Vidéos explicatives d'une ouverture | `GET /api/v1/videos/{opening}` | API YouTube Data v3 |
| Santé de l'API | `GET /api/v1/healthcheck` | — |

La documentation interactive (Swagger) est disponible sur http://localhost:8000/docs.

## Architecture

```
 Navigateur ──▶ frontend (nginx, port 4200) : application Angular + proxy /api/ ──┐
                                                                                  ▼
                         ┌────────────────────── API FastAPI (conteneur api) ──────────────────────┐
                         │                                                                          │
 /moves, /evaluate ────▶ │ ChessAgentService ──┬─▶ LichessService ──────────▶ explorer.lichess.org  │
                         │ (validation FEN     └─▶ StockfishService ────────▶ moteur Stockfish (UCI)│
                         │  avec python-chess)                                                      │
                         │                                                                          │
 /vector-search ───────▶ │ VectorSearchGraph (LangGraph)                                            │
                         │   analyze_query ─▶ embed_query ─▶ search_milvus ─▶ select_openings       │
                         │   (langue, nombre)  (Qwen3)        (Milvus)         ─┬─▶ suggest_videos   │
                         │                                                      └─▶ fin (sans vidéo) │
                         │                                                                          │
 /videos ──────────────▶ │ YouTubeService ─────────────────────────────────▶ YouTube Data API v3  │
                         └──────────────────────────────────────────────────────────────────────────┘
                                                   │
                         Milvus standalone (+ etcd, MinIO), chargé au démarrage par openings-loader
```

- **`frontend/`** : application Angular (voir [frontend/README.md](frontend/README.md)). nginx sert l'application et redirige `/api/` vers le conteneur `api` : même origine, pas de CORS.
- **`backend/api/api.py`** : routes FastAPI uniquement ; la logique métier est dans `backend/api/services/`.
- **`chess_agent.py`** : valide les FEN (python-chess), filtre les coups Lichess illégaux, délègue à Stockfish.
- **`lichess_service.py`** : appels à l'explorateur d'ouvertures avec token, délai minimal d'1 s entre deux requêtes, nouvelles tentatives sur 429, gestion des timeouts.
- **`stockfish_service.py`** : lance Stockfish via UCI, renvoie l'évaluation en centipawns (ou le mat en N coups) du point de vue des Blancs.
- **`embedding_service.py`** : modèle `Qwen/Qwen3-Embedding-0.6B` (sentence-transformers), prompt `query` pour les questions.
- **`milvus_service.py`** : collection `openings`, similarité cosinus.
- **`chunking.py`** : découpage des descriptions (voir [Corpus](#corpus-des-ouvertures)).
- **`rag_graph.py`** : graphe LangGraph de la recherche sémantique, avec une arête conditionnelle vers la suggestion de vidéos.
- **`youtube_service.py`** : recherche, filtrage et cache des vidéos, suivi du quota.
- **`scripts/load_openings.py`** : chargement du corpus dans Milvus (`--if-empty` au démarrage).

### LangGraph

Graphe utilisé dans le projet : 

```
START → analyze_query → embed_query → search_milvus → select_openings
                                                              │
                                              (route conditionnelle)
                                              ├── résultats + with_videos → suggest_videos → END
                                              └── sinon → END
```

## Utilisation de l'API

Les FEN contiennent des `/` et des espaces : les espaces doivent être encodés (`%20`), les `/` peuvent rester tels quels.

### Coups théoriques — `/api/v1/moves/{fen}`

```bash
curl "http://localhost:8000/api/v1/moves/rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR%20w%20KQkq%20-%200%201"
```

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "moves": [
    {"uci": "e2e4", "san": "e4", "white": 419328, "draws": 573290, "black": 316848},
    {"uci": "d2d4", "san": "d4", "white": 334470, "draws": 461840, "black": 233568}
  ],
  "opening": null
}
```

`white` / `draws` / `black` : nombre de parties de maîtres gagnées par les Blancs, nulles, gagnées par les Noirs. `opening` : ouverture nommée par Lichess pour cette position (`{"eco": "B90", "name": "Sicilian Defense: Najdorf Variation"}`), `null` si la position n'a pas de nom.

### Évaluation Stockfish — `/api/v1/evaluate/{fen}`

```bash
curl "http://localhost:8000/api/v1/evaluate/rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR%20w%20KQkq%20-%200%201"
```

```json
{"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "turn": "white", "depth": 15, "cp": 39, "mate": null}
```

`cp` : avantage en centipawns pour les Blancs ; `mate` : mat en N coups (négatif si les Noirs matent).

### Recherche sémantique — `/api/v1/vector-search`

| Paramètre | Défaut | Rôle |
|---|---|---|
| `query` | (obligatoire) | Question en langage naturel, en français ou en anglais |
| `top_k` | nombre demandé dans la question, sinon 5 | Nombre d'ouvertures renvoyées (1 à 10) |
| `with_videos` | `true` | Proposer jusqu'à 3 vidéos par ouverture |
| `lang` | langue détectée | `fr` ou `en` : impose la langue des passages et des vidéos |
| `eco` | — | Code ECO (`B90`) : si le corpus a des fiches pour ce code, la réponse les privilégie ; sinon, recherche sémantique |

```bash
curl "http://localhost:8000/api/v1/vector-search?query=Donne-moi%20deux%20exemples%20d%27ouverture%20simple"
```

Le graphe LangGraph :
1. détecte la langue de la question (français ou anglais, français par défaut) et le nombre d'ouvertures demandé (« deux exemples », *three openings*…) si `top_k` n'est pas fourni ;
2. cherche les passages dans Milvus et garde **un seul résultat par ouverture** (son meilleur passage) ;
3. cherche **jusqu'à 3 vidéos par ouverture, dans la langue de la question** (nom français pour une question en français). Toutes viennent d'une même recherche YouTube : 3 vidéos ne coûtent pas plus de quota qu'une seule.

Réponse : `lang` (langue retenue), `results` (nom EN/FR, code ECO, coups, `text` du meilleur passage, `description` reconstituée à partir des passages de l'ouverture trouvés dans la même langue, langue du passage, lien Wikipédia, score, `videos`) et `videos_message`, renseigné quand une ouverture n'a aucune vidéo ou que YouTube est indisponible. La recherche ne tombe pas en erreur pour autant.

### Vidéos — `/api/v1/videos/{opening}`

| Paramètre | Défaut | Rôle |
|---|---|---|
| `opening` | (obligatoire) | Nom de l'ouverture, de préférence en anglais (`Sicilian Defence`, `Ruy Lopez, Berlin Defence`) |
| `max_results` | 5 | Entre 1 et 10 |
| `lang` | — | `fr` ou `en` : mots-clés de recherche dans cette langue et vidéos dans cette langue uniquement |

```bash
curl "http://localhost:8000/api/v1/videos/Sicilian%20Defence"
```

Chaque vidéo contient : titre, chaîne, date, durée, vues, likes, miniature, `url` (page YouTube) et `embed_url` (lecture intégrée dans l'application). Si rien n'est trouvé : `videos: []` et un `message`.

**Recherche** : une seule requête par ouverture et par langue : `"<ouverture>" chess opening tutorial|explanation|explained` en anglais, `"<ouverture>" échecs ouverture|explication|tutoriel|cours` en français.
**Filtres** : vidéo publique et intégrable, pas de direct, durée de 3 min à 2 h (pas de Shorts), au moins 1 000 vues, mots distinctifs du nom (français ou anglais) présents dans le titre, la description ou les tags. Avec une langue demandée : langue audio déclarée sur YouTube (ou, à défaut, langue détectée du titre et de la description) identique, titre sans autre alphabet ni mention d'une autre langue (« in Hindi »…).
**Quota** : une recherche coûte 101 unités (quota par défaut : 10 000/jour). Les résultats sont mis en cache 24 h ; un compteur interne refuse les appels avant dépassement et la limite se réinitialise à minuit (heure du Pacifique).

### Codes d'erreur

| Code | Cas |
|---|---|
| 400 | FEN invalide ou position illégale |
| 422 | Paramètre invalide |
| 429 | Limite Lichess atteinte, ou quota YouTube épuisé (en-tête `Retry-After`) |
| 502 | Erreur d'un service externe (Lichess, Stockfish, Milvus, YouTube) |
| 503 | Clé YouTube non configurée |
| 504 | Délai dépassé (Lichess, YouTube) |

## Corpus des ouvertures

`data/openings.json` contient **70 ouvertures**, chacune avec :

| Champ | Contenu |
|---|---|
| `eco_code`, `moves_san` | Code ECO et coups (vérifiés avec python-chess) |
| `opening_name`, `opening_name_fr` | Noms anglais et français |
| `description`, `description_fr` | Introduction (ou section) de l'article Wikipédia, max ~1 500 caractères |
| `description_url`, `description_fr_url` | Liens vers les sources (licence CC BY-SA) |
| `source_url` | Origine de l'entrée (liste ECO Wikipédia ou ficgs.com) |

**Construction** : [scripts/build_openings_corpus.py](scripts/build_openings_corpus.py) part des entrées saisies à la main ([data/openings_seed.json](data/openings_seed.json)), ajoute les ouvertures nommées de la [liste des codes ECO](https://en.wikipedia.org/wiki/List_of_ECO_codes), récupère les descriptions anglaises puis leurs équivalents français (liens interlangues Wikipédia, ou table `FRENCH_ARTICLES` pour les variantes). Les ouvertures sans description française fiable sont écartées.

```bash
uv run --no-project --with httpx --with chess python scripts/build_openings_corpus.py
docker compose exec api python -m api.scripts.load_openings
```

**Chunking** : chaque description est découpée entre les paragraphes, par blocs de 800 caractères maximum, séparément en anglais et en français. Chaque chunk commence par un en-tête autoportant (noms FR/EN, code ECO, coups). 70 ouvertures donnent 268 chunks.

Les ouvertures au nom trop générique pour trouver une description ou des vidéos dédiées (C20 *Open Game*, D00 *Closed Game*) sont exclues (`EXCLUDED_ECO_CODES` dans le script).


## Limites connues et pistes

- Le cache des vidéos et le compteur de quota YouTube sont en mémoire : ils repartent à zéro au redémarrage de l'API.
- Certaines descriptions françaises sont moins riches que les anglaises (ex. gambit Benko) ; 10 ouvertures ont été écartées faute de version française.
- Le premier démarrage calcule les vecteurs du corpus sur CPU (~6 min).

## Structure du dépôt

```
.env.example                modèle du fichier .env (clés API, ports)
docker-compose.yml          orchestration de tous les services et volumes
backend/
  Dockerfile
  requirements.txt          dépendances Python (versions testées)
  api/
    api.py                  routes FastAPI
    schemas.py              modèles de réponse (Pydantic)
    services/               Lichess, Stockfish, embeddings, Milvus, chunking, LangGraph, YouTube
    scripts/load_openings.py  chargement du corpus dans Milvus
data/
  openings.json             corpus des ouvertures (généré)
  openings_seed.json        entrées saisies à la main
scripts/
  build_openings_corpus.py  construction du corpus depuis Wikipédia
  eval_vector_search.py     évaluation de /vector-search
frontend/
  Dockerfile, nginx.conf    build Angular puis service nginx (proxy /api/)
  src/app/core/             services : API, partie (chess.js), orchestration de l'agent
  src/app/board/            échiquier, contrôles et positions de démonstration
  src/app/agent-panel/      panneau de recommandations et vidéos
```

## Stack technique

Angular 22 · ngx-chess-board · chess.js · FastAPI · LangGraph · Milvus · sentence-transformers (Qwen3-Embedding-0.6B) · python-chess · Stockfish · API Lichess · API YouTube Data v3 · nginx · Docker Compose.
