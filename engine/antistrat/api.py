"""FastAPI app. Serves aggregate results only, never raw GRID data."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AntiStrat API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

MVP_MAPS = ["haven", "lotus"]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/maps")
def maps() -> dict:
    return {"maps": MVP_MAPS}
