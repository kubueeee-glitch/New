"""HUD (E6): FastAPI + WebSocket + jeden plik HTML. Bez frameworka JS,
bez build stepu."""
from __future__ import annotations

import asyncio
import json
import os

from .state import HudState

_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


def create_app(state: HudState):
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="Jarvis HUD")

    @app.get("/")
    async def index() -> HTMLResponse:
        with open(_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        try:
            while True:
                await socket.send_text(json.dumps(state.snapshot(), ensure_ascii=False))
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            pass

    return app


async def serve(state: HudState, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(create_app(state), host=host, port=port, log_level="warning")
    )
    await server.serve()
