from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import os, httpx

app = FastAPI()

AUTH_KEY = os.environ.get("AUTH_KEY", "")
BARK_KEY = os.environ.get("BARK_KEY", "")

store = {}

@app.get("/")
async def root():
    return {"status": "ok", "service": "health-server", "records": len(store)}

@app.post("/ingest")
@app.post("/ingest/{path:path}")
async def ingest(request: Request, path: str = ""):
    try:
        body = await request.json()
    except Exception:
        raw = await request.body()
        body = {"raw": raw.decode("utf-8", errors="replace")}

    ts = datetime.utcnow().isoformat()
    store[ts] = body

    # Bark push
    if BARK_KEY:
        title = "健康数据"
        msg = f"收到新数据 {ts}"
        url = f"https://api.day.app/{BARK_KEY}/{title}/{msg}"
        try:
            async with httpx.AsyncClient() as client:
                await client.get(url)
        except Exception:
            pass

    return JSONResponse({"status": "ok", "time": ts})

@app.get("/latest")
async def latest(k: str = ""):
    if k != AUTH_KEY:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not store:
        return JSONResponse({"status": "no data yet"})
    last_key = sorted(store.keys())[-1]
    return JSONResponse({"time": last_key, "data": store[last_key]})

@app.get("/all")
async def all_data(k: str = ""):
    if k != AUTH_KEY:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse({"records": len(store), "data": store})
