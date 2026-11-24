import re
from dataclasses import dataclass

# Padrões compilados na inicialização do módulo para evitar recompilação por requisição
_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CNPJ_PATTERN = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(
    r"\b(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\d{4}|\d{4})-?\d{4}\b"
)


@dataclass(frozen=True)
class SanitizationResult:
    sanitized_text: str
    redacted_count: int


def sanitize_pii(text: str) -> SanitizationResult:
    """
    Mascara dados pessoais identificáveis (PII) antes de enviar texto a LLMs externos.
    A ordem importa: CNPJ (14 dígitos) deve ser substituído antes de CPF (11 dígitos)
    para evitar casamento parcial de dígitos.
    """
    total_redactions = 0

    patterns: list[tuple[re.Pattern[str], str]] = [
        (_CNPJ_PATTERN, "[CNPJ_OCULTO]"),
        (_CPF_PATTERN, "[CPF_OCULTO]"),
        (_EMAIL_PATTERN, "[EMAIL_OCULTO]"),
        (_PHONE_PATTERN, "[TELEFONE_OCULTO]"),
    ]

    cleaned = text
    for pattern, placeholder in patterns:
        cleaned, count = pattern.subn(placeholder, cleaned)
        total_redactions += count

    return SanitizationResult(sanitized_text=cleaned, redacted_count=total_redactions)
