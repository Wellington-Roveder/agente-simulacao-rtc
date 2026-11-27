import httpx

from app.core.config import Settings
from app.core.errors import RFBUnavailableError, RFBValidationError
from app.schemas.fiscal import (
    OperacaoRegimeGeralInput,
    OperacaoSimplesInput,
    ResultadoObservabilidadeRFB,
)


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
                self._raise_for_rfb_status(response, "atividades_simples")
                return response.json()
            except httpx.RequestError as exc:
                raise RFBUnavailableError(
                    "Falha de rede ao consultar atividades SN."
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
                self._raise_for_rfb_status(response, "gerador_danfse")
                return response.content
            except httpx.RequestError as exc:
                raise RFBUnavailableError(
                    "Falha de rede ao comunicar com gerador DANFSe."
                ) from exc

    async def _post_calculo(self, url: str, body: dict) -> ResultadoObservabilidadeRFB:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(url, json=body)
                self._raise_for_rfb_status(response, "calculadora_rtc")
                return ResultadoObservabilidadeRFB.model_validate(response.json())
            except httpx.RequestError as exc:
                raise RFBUnavailableError(
                    "Falha de rede ao comunicar com calculadora RFB."
                ) from exc

    @staticmethod
    def _raise_for_rfb_status(response: httpx.Response, service_label: str) -> None:
        if response.is_success:
            return
        if 400 <= response.status_code < 500:
            raise RFBValidationError(
                f"Entrada rejeitada pelo serviço {service_label} (HTTP {response.status_code})."  # noqa: E501
            )
        raise RFBUnavailableError(
            f"Serviço {service_label} indisponível (HTTP {response.status_code})."
        )
