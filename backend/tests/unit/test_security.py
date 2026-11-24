from app.core.security import sanitize_pii


def test_sanitize_pii_masks_cpf_cnpj_and_email() -> None:
    raw = (
        "Vendi um curso de R$ 497,00 para João (CPF 123.456.789-00, "
        "email joao.silva@exemplo.com.br) pela empresa 12.345.678/0001-99."
    )

    result = sanitize_pii(raw)

    assert "123.456.789-00" not in result.sanitized_text
    assert "12.345.678/0001-99" not in result.sanitized_text
    assert "joao.silva@exemplo.com.br" not in result.sanitized_text
    assert "[CPF_OCULTO]" in result.sanitized_text
    assert "[CNPJ_OCULTO]" in result.sanitized_text
    assert "[EMAIL_OCULTO]" in result.sanitized_text
    assert "R$ 497,00" in result.sanitized_text
    assert result.redacted_count == 3


def test_sanitize_pii_preserves_clean_fiscal_text() -> None:
    raw = "Simule venda de mentoria online de R$ 1.200,00 no Simples Nacional em SP."

    result = sanitize_pii(raw)

    assert result.sanitized_text == raw
    assert result.redacted_count == 0
