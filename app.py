import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
app = FastAPI()

EXAMPLES = {"why_card", "overlay_cue"}


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/examples/{name}")
def example(name: str):
    if name not in EXAMPLES:
        raise HTTPException(status_code=404, detail="Unknown example")
    return json.loads((ROOT / "examples" / f"{name}.json").read_text())


# Keep this LAST, after all routes
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")