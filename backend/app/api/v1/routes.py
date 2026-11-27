from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings, get_settings
from app.core.errors import RateLimitExceededError
from app.services.cache_service import CacheService
from app.services.openai_agent import FiscalOrchestratorAgent
from app.services.rfb_client import RFBFiscalClient

router = APIRouter(prefix="/api/v1")


# --- Contratos da API Pública ---


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(..., min_length=1, max_length=4000)
    session_id: UUID | None = None


class ToolExecutionSummary(BaseModel):
    tool: str
    status: str


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    in_scope: bool
    pii_redacted_count: int
    tools_used: list[ToolExecutionSummary] = Field(default_factory=list)


class DanfseGenerateRequest(BaseModel):
    xml_nfse: str = Field(..., min_length=10, max_length=500_000)
    canhoto: bool = True


class DanfseGenerateResponse(BaseModel):
    download_token: str
    download_url: str
    expires_in_seconds: int


# --- Dependências ---


def get_agent(request: Request) -> FiscalOrchestratorAgent:
    return request.app.state.agent


def get_rfb_client(request: Request) -> RFBFiscalClient:
    return request.app.state.rfb_client


def get_cache_service(request: Request) -> CacheService:
    return request.app.state.cache_service


async def enforce_rate_limit(
    request: Request,
    cache: Annotated[CacheService, Depends(get_cache_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    client_ip = request.client.host if request.client else "unknown"
    allowed = await cache.check_rate_limit(
        identifier=client_ip,
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not allowed:
        raise RateLimitExceededError("Rate limit excedido para o IP.")


# --- Endpoints ---


@router.get("/health", tags=["Infra"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", tags=["Infra"])
async def readiness_check(
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> Response:
    redis_ok = await cache.ping()
    if not redis_ok:
        return Response(
            content='{"status":"unavailable","redis":false}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json",
        )
    return Response(
        content='{"status":"ready","redis":true}',
        status_code=status.HTTP_200_OK,
        media_type="application/json",
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    tags=["Simulação RTC"],
    dependencies=[Depends(enforce_rate_limit)],
)
async def chat_endpoint(
    body: ChatRequest,
    agent: Annotated[FiscalOrchestratorAgent, Depends(get_agent)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> ChatResponse:
    # Só reaproveita session_id se já existir no Redis; evita fixação de sessão
    session_id = uuid4().hex
    if body.session_id is not None:
        candidate = body.session_id.hex
        if await cache.get_session(candidate) is not None:
            session_id = candidate

    result = await agent.process_message(
        session_id=session_id,
        user_message=body.message,
    )
    summaries = [
        ToolExecutionSummary(
            tool=item["tool"],
            status="error"
            if "erro" in item.get("output", {})
            or "erro_execucao" in item.get("output", {})
            else "ok",
        )
        for item in result.tool_executions
    ]
    return ChatResponse(
        reply=result.reply,
        session_id=result.session_id,
        in_scope=result.in_scope,
        pii_redacted_count=result.pii_redacted_count,
        tools_used=summaries,
    )


@router.post(
    "/danfse",
    response_model=DanfseGenerateResponse,
    tags=["DANFSe"],
    dependencies=[Depends(enforce_rate_limit)],
)
async def gerar_danfse_endpoint(
    request: Request,
    body: DanfseGenerateRequest,
    rfb_client: Annotated[RFBFiscalClient, Depends(get_rfb_client)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DanfseGenerateResponse:
    pdf_bytes = await rfb_client.gerar_danfse_pdf(
        xml_nfse=body.xml_nfse,
        canhoto=body.canhoto,
    )
    token = uuid4().hex
    ttl = settings.danfse_ttl_seconds
    await cache.save_danfse_pdf(token=token, pdf_bytes=pdf_bytes, ttl_seconds=ttl)

    download_url = request.app.url_path_for("baixar_danfse_endpoint", token=token)
    return DanfseGenerateResponse(
        download_token=token,
        download_url=download_url,
        expires_in_seconds=ttl,
    )


@router.get("/danfse/{token}", tags=["DANFSe"])
async def baixar_danfse_endpoint(
    token: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> Response:
    pdf_bytes = await cache.get_danfse_pdf(token)
    if pdf_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF não encontrado ou expirado.",
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="danfse-{token[:8]}.pdf"',
            "Cache-Control": "no-store",
        },
    )
