import httpx
import pytest
import respx

from app.core.config import Settings
from app.schemas.fiscal import (
    EstadoItemCalculo,
    ItemRegimeGeralInput,
    OperacaoRegimeGeralInput,
)
from app.services.rfb_client import RFBFiscalClient


@pytest.mark.asyncio
@respx.mock
async def test_calcular_regime_regular_sucesso_e_inconsistencia() -> None:
    settings = Settings(rfb_regular_url="http://rfb-regular.test/api")
    client = RFBFiscalClient(settings)

    mock_response = {
        "objetos": [
            {
                "nObj": 1,
                "estadoItem": "CALCULO_SIMULADO",
                "tribCalc": {
                    "IBSCBS": {
                        "CST": "200",
                        "cClassTrib": "200028",
                        "gIBSCBS": {"vBC": "1200.00", "vIBS": "0.48", "vCBS": "42.24"},
                    }
                },
            },
            {
                "nObj": 2,
                "estadoItem": "INCONSISTENCIA_ENTRADA",
                "erros": [
                    {
                        "code": "REG-011",
                        "title": "NCM não vinculada",
                        "pointer": "#/itens/1/ncm",
                        "detail": "NCM incompatível com cClassTrib",
                    }
                ],
            },
        ],
        "total": {"tribCalc": {"IBSCBSTot": {"vBCIBSCBS": "1200.00"}}},
    }

    respx.post(
        "http://rfb-regular.test/api/calculadora/observabilidade/regime-geral"
    ).mock(return_value=httpx.Response(200, json=mock_response))

    payload = OperacaoRegimeGeralInput(
        dhFatoGerador="2027-03-10T10:00:00-03:00",
        municipio=3550308,
        uf="SP",
        itens=[
            ItemRegimeGeralInput(
                numero=1,
                nbs="122011200",
                cst="200",
                cClassTrib="200028",
                baseCalculo=1200.00,
            ),
            ItemRegimeGeralInput(
                numero=2,
                ncm="02013000",
                cst="200",
                cClassTrib="200035",
                baseCalculo=80.00,
            ),
        ],
    )

    resultado = await client.calcular_regime_regular(payload)

    assert len(resultado.objetos) == 2
    assert resultado.objetos[0].estadoItem == EstadoItemCalculo.CALCULO_SIMULADO
    assert resultado.objetos[1].estadoItem == EstadoItemCalculo.INCONSISTENCIA_ENTRADA
    assert resultado.objetos[1].erros[0].code == "REG-011"
