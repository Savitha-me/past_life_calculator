from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes.past_life import router as past_life_router
from core.database import connect_to_mongo, close_mongo_connection
from core.exceptions import ChartAPIError, LLMError
from core.logging_middleware import RequestLoggingMiddleware


# ---------- startup / shutdown (MongoDB connection) ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


# ---------- the ONE app instance ----------
app = FastAPI(title="Past Life Calculator", version="1.0.0", lifespan=lifespan)

# ---------- CORS: which websites may call this API from a browser ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://localhost:5173",
        "http://192.168.45.5:5173",
        "http://localhost:3000",
        "https://past-life-calculator-first.vercel.app",
        "https://past-life-calculator-copy.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(past_life_router)


# ---------- global error handling (routes stay clean) ----------
@app.exception_handler(ChartAPIError)  # also covers AuthenticationError
async def chart_api_error_handler(request: Request, exc: ChartAPIError):
    return JSONResponse(status_code=exc.status_code or 502, content={"detail": exc.message})


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# ---------- health check ----------
@app.get("/")
async def health():
    return {"status": "ok"}