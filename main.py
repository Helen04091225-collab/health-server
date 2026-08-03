import os
import json
import time
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

AUTH_KEY = os.environ.get("AUTH_KEY", "xiaoke2026")
BARK_KEY = os.environ.get("BARK_KEY", "")

health_data = []
MAX_RECORDS = 2000

@app.get("/")
async def root():
    return {"status": "ok", "service": "health-server", "records": len(health_data)}

@app.post("/ingest")
async def ingest(request: Request):
    try:
        body = await request.body()
        text = body.decode("utf-8", errors="replace")
        start = text.find("{")
        if start >= 0:
            data = json.loads(text[start:])
        else:
            data = json.loads(text)

        record = {
            "received_at": datetime.now().isoformat(),
            "timestamp": time.time(),
            "data": data
        }
        health_data.append(record)
        if len(health_data) > MAX_RECORDS:
            health_data[:] = health_data[-MAX_RECORDS:]

        await check_anomalies(data)
        return {"status": "ok", "records_stored": len(health_data)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/latest")
async def latest(k: str = ""):
    if k != AUTH_KEY:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not health_data:
        return {"status": "no data yet"}

    latest_record = health_data[-1]
    data = latest_record.get("data", {})
    metrics_list = data.get("data", {}).get("metrics", []) or data.get("metrics", [])

    snapshot = {}
    for m in metrics_list:
        name = m.get("name", "")
        points = m.get("data", [])
        if points:
            last_point = points[-1]
            snapshot[name] = {
                "value": last_point.get("qty", last_point.get("value")),
                "date": last_point.get("date", ""),
                "units": m.get("units", "")
            }
    return {"received_at": latest_record["received_at"], "snapshot": snapshot}

@app.get("/query")
async def query(k: str = "", metric: str = "", hours: int = 24):
    if k != AUTH_KEY:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    cutoff = time.time() - hours * 3600
    recent = [r for r in health_data if r["timestamp"] >= cutoff]

    if metric:
        results = []
        for record in recent:
            data = record.get("data", {})
            metrics_list = data.get("data", {}).get("metrics", []) or data.get("metrics", [])
            for m in metrics_list:
                if metric.lower() in m.get("name", "").lower():
                    results.append({
                        "name": m["name"],
                        "units": m.get("units", ""),
                        "data": m.get("data", [])[-10:],
                        "received_at": record["received_at"]
                    })
        return {"metric": metric, "results": results}

    summary = {
        "total_records": len(health_data),
        "recent_records": len(recent),
        "latest_received": health_data[-1]["received_at"] if health_data else None,
        "metrics_available": []
    }
    if health_data:
        latest_data = health_data[-1].get("data", {})
        metrics_list = latest_data.get("data", {}).get("metrics", []) or latest_data.get("metrics", [])
        summary["metrics_available"] = [m.get("name", "") for m in metrics_list]
    return summary

async def check_anomalies(data):
    if not BARK_KEY:
        return
    try:
        metrics_list = data.get("data", {}).get("metrics", []) or data.get("metrics", [])
        alerts = []
        for m in metrics_list:
            name = m.get("name", "")
            points = m.get("data", [])
            if not points:
                continue
            value = points[-1].get("qty")
            if value is None:
                continue
            if "heart_rate" in name.lower() and "resting" not in name.lower() and "variability" not in name.lower():
                if value > 130:
                    alerts.append(f"心率偏高: {value} bpm")
                elif value < 40:
                    alerts.append(f"心率偏低: {value} bpm")
            if "oxygen" in name.lower() and value < 94:
                alerts.append(f"血氧偏低: {value}%")
        if alerts:
            alert_text = " | ".join(alerts)
            url = f"https://api.day.app/{BARK_KEY}/健康提醒/{alert_text}"
            async with httpx.AsyncClient() as client:
                await client.get(url)
    except:
        pass

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

