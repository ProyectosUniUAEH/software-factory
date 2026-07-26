from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os

app = FastAPI(title="homepage-api")

static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')
if os.path.exists(static_dir):
    app.mount('/static', StaticFiles(directory=static_dir), name='static')


@app.get("/")
async def root():
    return {"message": "homepage-api is running", "service": "homepage-api"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/db-check")
async def db_check():
    """Validate MongoDB connectivity using injected secret env vars."""
    uri = os.environ.get("HOMEPAGE_DB_URI") or os.environ.get("MONGODB_URI") or ""
    db_name = os.environ.get("HOMEPAGE_DB_DATABASE", "test")
    info = {
        "uri_present": bool(uri),
        "uri_scheme": uri.split("://", 1)[0] if "://" in uri else None,
        "database": db_name,
    }
    if not uri:
        return {"ok": False, "reason": "no URI in env", **info}
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
        pong = await client.admin.command("ping")
        collections = await client[db_name].list_collection_names()
        client.close()
        return {"ok": True, "ping": pong, "collections": collections, **info}
    except Exception as e:
        return {"ok": False, "error": str(e), **info}


@app.get("/test-ws", response_class=HTMLResponse)
async def test_ws():
    sd = os.path.join(os.path.dirname(__file__), '..', 'static')
    tf = os.path.join(sd, 'test-websocket.html')
    if os.path.exists(tf):
        with open(tf) as f:
            return f.read()
    return "<h1>WebSocket test client not found</h1>"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except Exception:
        pass
    finally:
        await websocket.close()
