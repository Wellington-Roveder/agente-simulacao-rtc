from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import router as v1_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.services.cache_service import CacheService
from app.services.openai_agent import FiscalOrchestratorAgent
from app.services.rfb_client import RFBFiscalClient
from app.services.semantic_router import SemanticRouter

_MAX_BODY_BYTES = 600_000


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    cache_service = CacheService(settings)
    rfb_client = RFBFiscalClient(settings)
    semantic_router = SemanticRouter(settings)
    agent = FiscalOrchestratorAgent(
        settings=settings,
        rfb_client=rfb_client,
        cache_service=cache_service,
        semantic_router=semantic_router,
    )

    app.state.cache_service = cache_service
    app.state.rfb_client = rfb_client
    app.state.agent = agent

    yield

    await cache_service.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None if settings.environment == "production" else "/redoc",
        openapi_url=None
        if settings.environment == "production"
        else "/openapi.json",
    )

    register_error_handlers(app)

    @app.middleware("http")
    async def limit_payload_size(request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Payload excede o limite máximo permitido."},
            )
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)
    return app


app = create_app()
