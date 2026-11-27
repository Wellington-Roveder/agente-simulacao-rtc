from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError

from app.core.config import Settings
from app.services.cache_service import CacheService, CacheServiceError


@pytest.fixture
def mock_redis() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def cache_service(mock_redis: AsyncMock) -> CacheService:
    settings = Settings(session_ttl_seconds=900)
    return CacheService(settings=settings, redis_client=mock_redis)


@pytest.mark.asyncio
async def test_save_and_get_session(
    cache_service: CacheService, mock_redis: AsyncMock
) -> None:
    state = {"regime": "SIMPLES_NACIONAL", "mensagens": ["Olá"]}
    await cache_service.save_session("sess-123", state)

    mock_redis.set.assert_awaited_once()
    args, kwargs = mock_redis.set.call_args
    assert args[0] == "rtc:session:sess-123"
    assert isinstance(args[1], bytes)
    assert kwargs["ex"] == 900

    mock_redis.get.return_value = args[1]
    recovered = await cache_service.get_session("sess-123")
    assert recovered == state


@pytest.mark.asyncio
async def test_get_session_cache_miss_returns_none(
    cache_service: CacheService, mock_redis: AsyncMock
) -> None:
    mock_redis.get.return_value = None
    assert await cache_service.get_session("inexistente") is None


@pytest.mark.asyncio
async def test_save_and_get_danfse_pdf_bytes(
    cache_service: CacheService, mock_redis: AsyncMock
) -> None:
    fake_pdf = b"%PDF-1.7\nconteudo_binario_danfse"
    await cache_service.save_danfse_pdf("tok-abc", fake_pdf, ttl_seconds=600)

    mock_redis.set.assert_awaited_once_with("rtc:danfse:tok-abc", fake_pdf, ex=600)

    mock_redis.get.return_value = fake_pdf
    recovered = await cache_service.get_danfse_pdf("tok-abc")
    assert recovered == fake_pdf


@pytest.mark.asyncio
async def test_redis_error_raises_cache_service_error(
    cache_service: CacheService, mock_redis: AsyncMock
) -> None:
    mock_redis.get.side_effect = RedisError("Connection refused sess-erro")

    with pytest.raises(
        CacheServiceError, match="Falha ao recuperar sessão"
    ) as exc_info:
        await cache_service.get_session("sess-erro")
    assert "sess-erro" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_danfse_cache_errors_do_not_include_token(
    cache_service: CacheService, mock_redis: AsyncMock
) -> None:
    mock_redis.set.side_effect = RedisError("Connection refused")
    token = "sensitive-download-token"

    with pytest.raises(CacheServiceError) as exc_info:
        await cache_service.save_danfse_pdf(token, b"%PDF")

    assert token not in str(exc_info.value)
