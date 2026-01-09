import asyncio
import os
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse


@dataclass
class Backend:
    base_url: str
    inflight: int = 0
    ewma_ms: float = 0.0
    down_until: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def is_healthy(self, now: float) -> bool:
        return now >= self.down_until

    async def incr_inflight(self) -> None:
        async with self.lock:
            self.inflight += 1

    async def decr_inflight(self) -> None:
        async with self.lock:
            if self.inflight > 0:
                self.inflight -= 1

    async def update_ewma(self, latency_ms: float, alpha: float) -> None:
        async with self.lock:
            if self.ewma_ms == 0.0:
                self.ewma_ms = latency_ms
            else:
                self.ewma_ms = (alpha * latency_ms) + ((1 - alpha) * self.ewma_ms)

    async def mark_down(self, cooldown_sec: float) -> None:
        async with self.lock:
            self.down_until = time.monotonic() + cooldown_sec


app = FastAPI()
client: Optional[httpx.AsyncClient] = None


def _get_env(name: str, legacy_name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None:
        return value
    return os.getenv(legacy_name, default)


def _parse_backends() -> List[Backend]:
    raw = _get_env("LLM_ROUTER_BACKENDS", "QWEN_ROUTER_BACKENDS", "").strip()
    if not raw:
        return []
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    return [Backend(base_url=u) for u in urls]


def _filter_request_headers(headers: Dict[str, str]) -> Dict[str, str]:
    excluded = {"host", "content-length", "connection"}
    return {k: v for k, v in headers.items() if k.lower() not in excluded}


def _filter_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    excluded = {"content-length", "transfer-encoding", "connection"}
    return {k: v for k, v in headers.items() if k.lower() not in excluded}


def _choose_backend(backends: List[Backend], latency_weight: float) -> Optional[Backend]:
    now = time.monotonic()
    healthy = [b for b in backends if b.is_healthy(now)]
    if not healthy:
        return None
    if len(healthy) == 1:
        return healthy[0]
    a, b = random.sample(healthy, 2)

    def score(backend: Backend) -> float:
        return backend.inflight + (latency_weight * backend.ewma_ms)

    return a if score(a) <= score(b) else b


@app.on_event("startup")
async def _startup() -> None:
    global client
    timeout = float(_get_env("LLM_ROUTER_TIMEOUT_SEC", "QWEN_ROUTER_TIMEOUT_SEC", "120"))
    connect_timeout = float(_get_env("LLM_ROUTER_CONNECT_TIMEOUT_SEC", "QWEN_ROUTER_CONNECT_TIMEOUT_SEC", "5"))
    limits = httpx.Limits(max_connections=256, max_keepalive_connections=64)
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=connect_timeout),
        limits=limits,
    )
    app.state.backends = _parse_backends()


@app.on_event("shutdown")
async def _shutdown() -> None:
    if client is not None:
        await client.aclose()


@app.get("/health")
async def health() -> JSONResponse:
    backends: List[Backend] = app.state.backends
    now = time.monotonic()
    return JSONResponse(
        {
            "status": "ok",
            "backends": [
                {
                    "base_url": b.base_url,
                    "healthy": b.is_healthy(now),
                    "inflight": b.inflight,
                    "ewma_ms": round(b.ewma_ms, 2),
                }
                for b in backends
            ],
        }
    )


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(path: str, request: Request) -> Response:
    if client is None:
        return JSONResponse({"error": "router not initialized"}, status_code=500)

    backends: List[Backend] = app.state.backends
    if not backends:
        return JSONResponse({"error": "no backends configured"}, status_code=503)

    latency_weight = float(_get_env("LLM_ROUTER_LATENCY_WEIGHT", "QWEN_ROUTER_LATENCY_WEIGHT", "0.001"))
    ewma_alpha = float(_get_env("LLM_ROUTER_EWMA_ALPHA", "QWEN_ROUTER_EWMA_ALPHA", "0.2"))
    cooldown_sec = float(_get_env("LLM_ROUTER_COOLDOWN_SEC", "QWEN_ROUTER_COOLDOWN_SEC", "5"))
    max_retries = int(_get_env("LLM_ROUTER_MAX_RETRIES", "QWEN_ROUTER_MAX_RETRIES", "1"))
    retry_statuses = {500, 502, 503, 504, 429}

    body = await request.body()
    headers = _filter_request_headers(dict(request.headers))

    tried: List[Backend] = []
    attempt = 0
    while attempt <= max_retries:
        backend = _choose_backend([b for b in backends if b not in tried], latency_weight)
        if backend is None:
            return JSONResponse({"error": "no healthy backends"}, status_code=503)
        tried.append(backend)
        attempt += 1

        await backend.incr_inflight()
        start = time.monotonic()
        try:
            url = backend.base_url.rstrip("/") + "/" + path
            if request.url.query:
                url += "?" + request.url.query

            cm = client.stream(
                request.method,
                url,
                headers=headers,
                content=body,
            )
            resp = await cm.__aenter__()
            if resp.status_code in retry_statuses and attempt <= max_retries:
                await backend.mark_down(cooldown_sec)
                await backend.decr_inflight()
                await resp.aclose()
                await cm.__aexit__(None, None, None)
                continue

            resp_headers = _filter_response_headers(dict(resp.headers))

            async def stream() -> bytes:
                try:
                    async for chunk in resp.aiter_raw():
                        yield chunk
                finally:
                    latency_ms = (time.monotonic() - start) * 1000
                    await backend.update_ewma(latency_ms, ewma_alpha)
                    await backend.decr_inflight()
                    await resp.aclose()
                    await cm.__aexit__(None, None, None)

            return StreamingResponse(stream(), status_code=resp.status_code, headers=resp_headers)
        except Exception:
            await backend.mark_down(cooldown_sec)
            await backend.decr_inflight()
            if attempt > max_retries:
                return JSONResponse({"error": "upstream request failed"}, status_code=502)

    return JSONResponse({"error": "upstream request failed"}, status_code=502)
