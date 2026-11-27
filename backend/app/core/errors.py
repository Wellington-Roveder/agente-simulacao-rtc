import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Base para exceções controladas da aplicação."""


class CacheServiceError(DomainError):
    """Erro de comunicação ou operação com o servidor Redis."""


class RFBClientError(DomainError):
    """Erro base na integração com os motores da Receita Federal."""


class RFBValidationError(RFBClientError):
    """O motor da RFB rejeitou a entrada enviada (4xx)."""


class RFBUnavailableError(RFBClientError):
    """Timeout, falha de rede ou erro interno (5xx) nos motores da RFB."""


class LLMProviderError(DomainError):
    """Falha de comunicação, timeout ou rate limit no provedor de LLM."""


class RateLimitExceededError(DomainError):
    """Cliente excedeu o limite de requisições na janela configurada."""


_ERROR_MAP: dict[type[DomainError], tuple[int, str]] = {
    RateLimitExceededError: (
        429,
        "Limite de requisições excedido. Tente novamente em instantes.",
    ),
    RFBValidationError: (
        422,
        "Não foi possível processar os dados fiscais ou XML enviados.",
    ),
    RFBUnavailableError: (
        503,
        "Motor de cálculo da Receita Federal temporariamente indisponível.",
    ),
    LLMProviderError: (502, "Serviço de interpretação temporariamente indisponível."),
    CacheServiceError: (503, "Serviço de sessão temporariamente indisponível."),
}


def register_error_handlers(app: FastAPI) -> None:
    for exc_class, (status_code, public_detail) in _ERROR_MAP.items():

        async def _handler(
            request: Request,
            exc: Exception,
            code: int = status_code,
            detail: str = public_detail,
        ) -> JSONResponse:
            logger.error(
                "Erro tratado em %s %s [%s]",
                request.method,
                request.url.path,
                type(exc).__name__,
                exc_info=exc,
            )
            return JSONResponse(status_code=code, content={"detail": detail})

        app.add_exception_handler(exc_class, _handler)
