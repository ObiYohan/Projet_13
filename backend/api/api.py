from fastapi import FastAPI

app = FastAPI()


@app.get("/api/v1/healthcheck")
def healthcheck():
    return {"status": "ok"}
