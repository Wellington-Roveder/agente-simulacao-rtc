import json
from typing import Any

from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.errors import CacheServiceError


class CacheService:
    """
    Gerencia estado efêmero de sessão (LGPD), cache de tabelas fiscais
    e armazenamento temporário de PDFs do DANFSe no Redis.
    """

    def __init__(self, settings: Settings, redis_client: Redis | None = None) -> None:
        self._session_ttl = settings.session_ttl_seconds
        # decode_responses=False preserva bytes puros para os PDFs do DANFSe
        self._redis: Redis = redis_client or from_url(
            settings.redis_url,
            decode_responses=False,
        )

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"rtc:session:{session_id}"

    @staticmethod
    def _fiscal_key(table_name: str) -> str:
        return f"rtc:fiscal:{table_name}"

    @staticmethod
    def _danfse_key(token: str) -> str:
        return f"rtc:danfse:{token}"

    # --- Sessão de Chat Efêmera (LGPD) ---

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        try:
            raw = await self._redis.get(self._session_key(session_id))
            if raw is None:
                return None
            return json.loads(raw.decode("utf-8"))
        except (RedisError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CacheServiceError("Falha ao recuperar sessão.") from exc

    async def save_session(
        self, session_id: str, state: dict[str, Any], ttl_seconds: int | None = None
    ) -> None:
        ttl = ttl_seconds or self._session_ttl
        try:
            payload = json.dumps(state, ensure_ascii=False).encode("utf-8")
            await self._redis.set(self._session_key(session_id), payload, ex=ttl)
        except RedisError as exc:
            raise CacheServiceError("Falha ao salvar sessão.") from exc

    async def delete_session(self, session_id: str) -> None:
        try:
            await self._redis.delete(self._session_key(session_id))
        except RedisError as exc:
            raise CacheServiceError("Falha ao remover sessão.") from exc

    # --- Cache de Tabelas Fiscais da RFB ---

    async def get_fiscal_table(self, table_name: str) -> Any | None:
        try:
            raw = await self._redis.get(self._fiscal_key(table_name))
            if raw is None:
                return None
            return json.loads(raw.decode("utf-8"))
        except (RedisError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CacheServiceError(
                f"Falha ao ler tabela fiscal '{table_name}': {exc}"
            ) from exc

    async def set_fiscal_table(
        self, table_name: str, data: Any, ttl_seconds: int = 86400
    ) -> None:
        try:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            await self._redis.set(self._fiscal_key(table_name), payload, ex=ttl_seconds)
        except RedisError as exc:
            raise CacheServiceError(
                f"Falha ao gravar tabela fiscal '{table_name}': {exc}"
            ) from exc

    # --- Armazenamento Temporário de PDF (DANFSe) ---

    async def save_danfse_pdf(
        self, token: str, pdf_bytes: bytes, ttl_seconds: int = 600
    ) -> None:
        try:
            await self._redis.set(self._danfse_key(token), pdf_bytes, ex=ttl_seconds)
        except RedisError as exc:
            raise CacheServiceError("Falha ao armazenar PDF.") from exc

    async def get_danfse_pdf(self, token: str) -> bytes | None:
        try:
            return await self._redis.get(self._danfse_key(token))
        except RedisError as exc:
            raise CacheServiceError("Falha ao recuperar PDF.") from exc

    async def close(self) -> None:
        await self._redis.aclose()

    async def check_rate_limit(
        self, identifier: str, max_requests: int, window_seconds: int
    ) -> bool:
        key = f"rtc:ratelimit:{identifier}"
        try:
            current = await self._redis.incr(key)
            if current == 1:
                await self._redis.expire(key, window_seconds)
            return int(current) <= max_requests
        except RedisError as exc:
            raise CacheServiceError("Falha ao verificar limite de taxa.") from exc

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except RedisError:
            return False
