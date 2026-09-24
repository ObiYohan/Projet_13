FROM python:3.14-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/*

ENV STOCKFISH_PATH=/usr/games/stockfish
ENV PYTHONPATH=/app
ENV HF_HOME=/root/.cache/huggingface

RUN pip install fastapi uvicorn httpx chess pymilvus langgraph
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install sentence-transformers
RUN pip install google-api-python-client tzdata

COPY backend/api ./api

CMD ["uvicorn", "api.api:app", "--host", "0.0.0.0", "--port", "8000"]
