from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RegimeTributario(StrEnum):
    SIMPLES_NACIONAL = "SIMPLES_NACIONAL"
    REGIME_REGULAR = "REGIME_REGULAR"


class EstadoItemCalculo(StrEnum):
    CALCULADO = "CALCULADO"
    CALCULO_SIMULADO = "CALCULO_SIMULADO"
    NAO_CALCULADO = "NAO_CALCULADO"
    INCONSISTENCIA_ENTRADA = "INCONSISTENCIA_ENTRADA"
    NAO_IMPLEMENTADO = "NAO_IMPLEMENTADO"
    FALHA_TECNICA = "FALHA_TECNICA"


# --- Contratos de Entrada: Regime Regular ---


class AliquotasNominaisInput(BaseModel):
    cbs: float = Field(default=8.8, description="Alíquota nominal CBS (%)")
    ibsEstadual: float = Field(default=0.05, description="Alíquota nominal IBS UF (%)")
    ibsMunicipal: float = Field(
        default=0.05, description="Alíquota nominal IBS Mun (%)"
    )


class ItemRegimeGeralInput(BaseModel):
    numero: int = Field(default=1, ge=1)
    nbs: str | None = Field(
        default=None, description="Código NBS para serviços (ex: 122011200)"
    )
    ncm: str | None = Field(default=None, description="Código NCM para mercadorias")
    cst: str = Field(
        ..., min_length=3, max_length=3, description="CST IBS/CBS (ex: 000, 200)"
    )
    cClassTrib: str = Field(
        ..., min_length=6, max_length=6, description="Classificação Tributária"
    )
    baseCalculo: float = Field(..., gt=0)
    quantidade: float = Field(default=1.0, gt=0)
    unidade: str = Field(default="UN")
    aliquotasNominais: AliquotasNominaisInput = Field(
        default_factory=AliquotasNominaisInput
    )


class OperacaoRegimeGeralInput(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    versao: str = "1.0.0"
    dhFatoGerador: str = Field(
        ..., description="Data/hora ISO-8601 (ex: 2027-03-10T10:00:00-03:00)"
    )
    municipio: int = Field(
        ..., description="Código IBGE do município (ex: 3550308 para SP)"
    )
    uf: str = Field(..., min_length=2, max_length=2)
    itens: list[ItemRegimeGeralInput] = Field(..., min_length=1)


# --- Contratos de Entrada: Simples Nacional (NT 2026.005) ---


class ItemSimplesInput(BaseModel):
    numero: int = Field(default=1, ge=1)
    cAtivSN: str | None = Field(
        default="01", description="Código de atividade SN (2 dígitos)"
    )
    cClassTrib: str = Field(default="000001", min_length=6, max_length=6)
    baseCalculo: str = Field(
        ..., description="Decimal formatado como string (ex: '497.00')"
    )
    valorImpostoSeletivo: str = Field(default="0.00")
    pIBSSN: str | None = Field(default=None, description="Alíquota efetiva IBS SN (%)")
    pCBSSN: str | None = Field(default=None, description="Alíquota efetiva CBS SN (%)")


class OperacaoSimplesInput(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    versao: str = "2.0.0"
    data: str = Field(..., description="Data do fato gerador YYYY-MM-DD")
    tpDoc: str = Field(default="55", description="Tipo DF-e: 55 (NF-e) ou 65 (NFC-e)")
    CRT: str = Field(default="1", description="1=Simples Nacional, 2=Excesso sublimite")
    tpRegimeIBSCBS: str | None = Field(default=None)
    tpEnteGov: str | None = Field(default=None)
    itens: list[ItemSimplesInput] = Field(..., min_length=1)


# --- Contratos de Saída (Observabilidade RFB) ---


class ErroObservabilidadeRFB(BaseModel):
    code: str
    title: str
    pointer: str | None = None
    detail: str


class ObjetoCalculadoRFB(BaseModel):
    nObj: int
    estadoItem: EstadoItemCalculo
    tribCalc: dict[str, Any] | None = None
    erros: list[ErroObservabilidadeRFB] = Field(default_factory=list)


class ResultadoObservabilidadeRFB(BaseModel):
    objetos: list[ObjetoCalculadoRFB] = Field(default_factory=list)
    total: dict[str, Any] | None = None
