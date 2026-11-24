import httpx

from app.core.config import Settings
from app.schemas.fiscal import (
    OperacaoRegimeGeralInput,
    OperacaoSimplesInput,
    ResultadoObservabilidadeRFB,
)


class RFBClientError(Exception):
    """Erro de comunicação ou resposta inesperada dos motores da Receita Federal."""


class RFBFiscalClient:
    def __init__(self, settings: Settings) -> None:
        self._regular_url = str(settings.rfb_regular_url).rstrip("/")
        self._simples_url = str(settings.rfb_simples_url).rstrip("/")
        self._danfse_url = str(settings.rfb_danfse_url).rstrip("/")
        self._timeout = httpx.Timeout(settings.rfb_timeout_seconds)

    async def calcular_regime_regular(
        self, payload: OperacaoRegimeGeralInput
    ) -> ResultadoObservabilidadeRFB:
        url = f"{self._regular_url}/calculadora/observabilidade/regime-geral"
        return await self._post_calculo(url, payload.model_dump(exclude_none=True))

    async def calcular_simples_nacional(
        self, payload: OperacaoSimplesInput
    ) -> ResultadoObservabilidadeRFB:
        url = f"{self._simples_url}/calculadora/observabilidade/simples-nacional"
        return await self._post_calculo(url, payload.model_dump(exclude_none=True))

    async def listar_atividades_simples(self, data_vigencia: str) -> list[dict]:
        url = f"{self._simples_url}/calculadora/simples-nacional/atividades"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.get(url, params={"data": data_vigencia})
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                raise RFBClientError(
                    f"Falha ao consultar atividades SN: {exc}"
                ) from exc

    async def gerar_danfse_pdf(self, xml_nfse: str, canhoto: bool = True) -> bytes:
        url = f"{self._danfse_url}/api/danfse"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    url,
                    params={"canhoto": str(canhoto).lower()},
                    content=xml_nfse.encode("utf-8"),
                    headers={"Content-Type": "application/xml"},
                )
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as exc:
                raise RFBClientError(f"Falha ao gerar PDF DANFSe: {exc}") from exc

    async def _post_calculo(self, url: str, body: dict) -> ResultadoObservabilidadeRFB:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(url, json=body)
                response.raise_for_status()
                return ResultadoObservabilidadeRFB.model_validate(response.json())
            except httpx.HTTPError as exc:
                raise RFBClientError(
                    f"Erro na comunicação com motor RFB ({url}): {exc}"
                ) from exc
