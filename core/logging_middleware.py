"""core/middleware.py

Prints every request and its response in the terminal:

======================================================================
📥 INCOMING REQUEST
   Method: POST
   Path:   /past-life/report
   Body:   { ...the JSON that was sent... }
📤 RESPONSE
   Status:   200
   Duration: 0.183 seconds
======================================================================

Written as a plain ASGI middleware so the request body can be read here
and still reach the endpoint unchanged.
"""
import json
import time

SEPARATOR = "=" * 70


def _safe_print(text: str) -> None:
    """print() that never crashes on terminals that cannot show emojis."""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"), flush=True)


class RequestLoggingMiddleware:
    def __init__(self, app, max_body_chars: int = 5000):
        self.app = app
        self.max_body_chars = max_body_chars

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":          # websockets etc. pass straight through
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()

        # ---- read the whole request body
        chunks = []
        while True:
            message = await receive()
            if message["type"] != "http.request":   # client disconnected
                break
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)

        # ---- give the same body to the endpoint
        delivered = False

        async def replay_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        # ---- remember the response status
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, replay_receive, send_wrapper)
        finally:
            self._log(scope, body, status_code, time.perf_counter() - started)

    # ------------------------------------------------------------------
    def _format_body(self, body: bytes) -> str:
        if not body:
            return "{}"
        text = body.decode("utf-8", errors="replace")
        try:
            text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except ValueError:
            pass  # not JSON: show it as it is
        if len(text) > self.max_body_chars:
            text = text[: self.max_body_chars] + "... (truncated)"
        return text

    def _log(self, scope, body: bytes, status_code: int, duration: float) -> None:
        path = scope["path"]
        query = scope.get("query_string", b"").decode("utf-8", errors="replace")
        if query:
            path = f"{path}?{query}"

        _safe_print("\n".join([
            SEPARATOR,
            "📥 INCOMING REQUEST",
            f"   Method: {scope['method']}",
            f"   Path:   {path}",
            f"   Body:   {self._format_body(body)}",
            "📤 RESPONSE",
            f"   Status:   {status_code}",
            f"   Duration: {duration:.3f} seconds",
            SEPARATOR,
        ]))