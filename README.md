# Agent IA d'apprentissage des ouvertures d'échecs

Agent intelligent qui accompagne les jeunes joueurs dans l'apprentissage des ouvertures : coups théoriques, évaluation de la position, contexte historique et stratégique, vidéos explicatives.

> **État d'avancement** : le backend (API FastAPI, Stockfish, Lichess, RAG Milvus, vidéos YouTube) est fonctionnel. L'interface Angular (échiquier interactif), le stockage MongoDB et l'analyse des vidéos (extraction de FEN depuis les images) restent à développer.

## Fonctionnalités

| Fonctionnalité | Endpoint | Source |
|---|---|---|
| Coups théoriques d'une position | `GET /api/v1/moves/{fen}` | API Lichess (base *masters*) |
| Évaluation d'une position | `GET /api/v1/evaluate/{fen}` | Stockfish (profondeur 15) |
| Recherche sémantique sur les ouvertures, avec vidéos suggérées | `GET /api/v1/vector-search?query=...` | Milvus + LangGraph |
| Vidéos explicatives d'une ouverture | `GET /api/v1/videos/{opening}` | API YouTube Data v3 |
| Santé de l'API | `GET /api/v1/healthcheck` | — |

La documentation interactive (Swagger) est disponible sur http://localhost:8000/docs une fois l'API lancée.

## Architecture

```
                         ┌────────────────────── API FastAPI (conteneur api) ──────────────────────┐
                         │                                                                          │
 /moves, /evaluate ────▶ │ ChessAgentService ──┬─▶ LichessService ──────────▶ explorer.lichess.org  │
                         │ (validation FEN     └─▶ StockfishService ────────▶ moteur Stockfish (UCI)│
                         │  avec python-chess)                                                      │
                         │                                                                          │
 /vector-search ───────▶ │ VectorSearchGraph (LangGraph)                                            │
                         │   embed_query ─▶ search_milvus ─▶ format_response ─┬─▶ suggest_videos    │
                         │   (Qwen3-Embedding)  (Milvus)                      └─▶ fin (sans vidéos) │
                         │                                                                          │
 /videos ──────────────▶ │ YouTubeService ─────────────────────────────────▶ YouTube Data API v3  │
                         └──────────────────────────────────────────────────────────────────────────┘
                                                   │
                         Milvus standalone (+ etcd, MinIO) sur le réseau Docker « milvus »
```

- **`backend/api/api.py`** : routes FastAPI uniquement ; la logique métier est dans `backend/api/services/`.
- **`chess_agent.py`** : valide les FEN (python-chess), filtre les coups Lichess illégaux, délègue à Stockfish.
- **`lichess_service.py`** : appels à l'explorateur d'ouvertures avec token, délai minimal d'1 s entre deux requêtes, nouvelles tentatives sur 429, gestion des timeouts.
- **`stockfish_service.py`** : lance Stockfish via UCI, renvoie l'évaluation en centipawns (ou le mat en N coups) du point de vue des Blancs.
- **`embedding_service.py`** : modèle `Qwen/Qwen3-Embedding-0.6B` (sentence-transformers), prompt `query` pour les questions.
- **`milvus_service.py`** : collection `openings`, similarité cosinus.
- **`chunking.py`** : découpage des descriptions (voir [Corpus](#corpus-des-ouvertures)).
- **`rag_graph.py`** : graphe LangGraph de la recherche sémantique, avec une arête conditionnelle vers la suggestion de vidéos.
- **`youtube_service.py`** : recherche, filtrage et cache des vidéos, suivi du quota.

## Prérequis

- Docker et Docker Compose
- Un token API Lichess : https://lichess.org/account/oauth/token (aucun scope nécessaire)
- Une clé API YouTube Data v3 (Google Cloud Console)
- ~5 Go d'espace disque (image avec PyTorch CPU, modèle d'embedding, Milvus)
- Pour les scripts de données : Python 3.14 et [uv](https://docs.astral.sh/uv/)

## Configuration

Créer un fichier `.env` à la racine (il est ignoré par git) :

```env
API_PORT=8000
LICHESS_API_TOKEN=<token Lichess>
API_KEY_YOUTUBE=<clé YouTube Data v3>
MILVUS_HOST=standalone
MILVUS_PORT=19530
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B

# Optionnel
# YOUTUBE_DAILY_QUOTA=10000        # unités par jour (défaut : 10000)
# YOUTUBE_CACHE_TTL_SECONDS=86400  # durée du cache des vidéos (défaut : 24 h)
```

`MILVUS_HOST=standalone` est le nom du service Milvus dans `docker-compose.yml` : l'API le joint par ce nom sur le réseau Docker.

## Lancement

```bash
# 1. Construire et démarrer la stack (api, milvus standalone, etcd, minio)
docker compose up -d --build

# 2. Charger le corpus des ouvertures dans Milvus (à refaire après chaque modification de data/openings.json)
docker compose exec api python -m api.scripts.load_openings

# 3. Vérifier
curl http://localhost:8000/api/v1/healthcheck
```

Au premier démarrage, le modèle d'embedding (~1,2 Go) est téléchargé depuis Hugging Face ; il est ensuite conservé dans le volume Docker `hf_cache`. L'API attend que Milvus soit sain (*healthcheck*) avant de démarrer.

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
  ]
}
```

`white` / `draws` / `black` : nombre de parties de maîtres gagnées par les Blancs, nulles, gagnées par les Noirs.

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

```bash
curl "http://localhost:8000/api/v1/vector-search?query=Donne-moi%20deux%20exemples%20d%27ouverture%20simple"
```

Le graphe LangGraph :
1. détecte la langue de la question (français ou anglais, français par défaut) et le nombre d'ouvertures demandé (« deux exemples », *three openings*…) si `top_k` n'est pas fourni ;
2. cherche les passages dans Milvus et garde **un seul résultat par ouverture** (son meilleur passage) ;
3. cherche **jusqu'à 3 vidéos par ouverture, dans la langue de la question** (nom français pour une question en français). Toutes viennent d'une même recherche YouTube : 3 vidéos ne coûtent pas plus de quota qu'une seule.

Réponse : `lang` (langue détectée), `results` (nom EN/FR, code ECO, coups, texte du passage, langue du passage, lien Wikipédia, score, `videos`) et `videos_message`, renseigné quand une ouverture n'a aucune vidéo ou que YouTube est indisponible. La recherche ne tombe pas en erreur pour autant.

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

## Tests

Évaluation de la recherche sémantique (stack lancée et corpus chargé) : une question réussit si l'ouverture attendue figure dans le top 3.

```bash
python scripts/eval_vector_search.py            # options : --top-k 5, --url http://...
```

Résultat actuel : **2/3**. La question sur le gambit Benko en français échoue (limite connue, voir ci-dessous).

## Limites connues et pistes

- Certaines descriptions françaises sont moins riches que les anglaises.
- Le cache des vidéos et le compteur de quota YouTube sont en mémoire : ils repartent à zéro au redémarrage (persistance MongoDB prévue).

Le détail des pistes d'amélioration est tenu à jour dans [CLAUDE.md](CLAUDE.md).

## Structure du dépôt

```
backend/
  Dockerfile
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
frontend/                   interface Angular (à venir)
docker-compose.yml          api + Milvus standalone (etcd, MinIO)
```

## Stack technique

FastAPI · LangGraph · Milvus · sentence-transformers (Qwen3-Embedding-0.6B) · python-chess · Stockfish · API Lichess · API YouTube Data v3 · Docker Compose. MongoDB est prévu pour le stockage des vidéos.
