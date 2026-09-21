FROM python:3.14-slim

WORKDIR /app

RUN pip install fastapi uvicorn

COPY backend/api/api.py ./api.py

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
