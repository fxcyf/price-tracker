from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cookies, parse, prices, products, settings, watch
from app.core.config import get_settings

_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=_settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/api")
app.include_router(prices.router, prefix="/api")
app.include_router(watch.router, prefix="/api")
app.include_router(parse.router, prefix="/api")
app.include_router(cookies.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
