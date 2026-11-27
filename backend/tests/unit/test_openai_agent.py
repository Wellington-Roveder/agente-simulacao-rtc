import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.core.errors import RFBUnavailableError
from app.schemas.fiscal import (
    EstadoItemCalculo,
    ObjetoCalculadoRFB,
    ResultadoObservabilidadeRFB,
)
from app.services.openai_agent import FiscalOrchestratorAgent


def _make_text_completion(content: str) -> SimpleNamespace:
    msg = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _make_tool_completion(call_id: str, fn_name: str, args: dict) -> SimpleNamespace:
    fn = SimpleNamespace(name=fn_name, arguments=json.dumps(args))
    tool_call = SimpleNamespace(id=call_id, function=fn)
    msg = SimpleNamespace(
        content=None,
        tool_calls=[tool_call],
        model_dump=lambda **_: {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": fn_name, "arguments": json.dumps(args)},
                }
            ],
        },
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


@pytest.mark.asyncio
async def test_agent_blocks_offtopic_without_calling_llm() -> None:
    mock_llm = MagicMock()
    mock_llm.chat.completions.create = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.get_session.return_value = None

    mock_router = MagicMock()
    mock_router.is_in_scope.return_value = (False, 0.12)

    agent = FiscalOrchestratorAgent(
        settings=Settings(),
        rfb_client=AsyncMock(),
        cache_service=mock_cache,
        semantic_router=mock_router,
        openai_client=mock_llm,
    )

    res = await agent.process_message("sess-1", "Qual a capital da França?")

    assert res.in_scope is False
    mock_llm.chat.completions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_redacts_pii_and_executes_rfb_tool() -> None:
    tool_args = {
        "dhFatoGerador": "2027-03-10T10:00:00-03:00",
        "municipio": 3550308,
        "uf": "SP",
        "itens": [
            {
                "numero": 1,
                "nbs": "122011200",
                "cst": "200",
                "cClassTrib": "200028",
                "baseCalculo": 1000.0,
            }
        ],
    }

    mock_llm = MagicMock()
    mock_llm.chat.completions.create = AsyncMock(
        side_effect=[
            _make_tool_completion("call_1", "simular_regime_regular", tool_args),
            _make_text_completion(
                "Simulação concluída: CBS de R$ 35,20 e IBS de R$ 0,40."
            ),
        ]
    )

    mock_rfb = AsyncMock()
    mock_rfb.calcular_regime_regular.return_value = ResultadoObservabilidadeRFB(
        objetos=[
            ObjetoCalculadoRFB(
                nObj=1,
                estadoItem=EstadoItemCalculo.CALCULO_SIMULADO,
                tribCalc={"IBSCBS": {"gIBSCBS": {"vCBS": "35.20", "vIBS": "0.40"}}},
            )
        ]
    )

    mock_cache = AsyncMock()
    mock_cache.get_session.return_value = None

    mock_router = MagicMock()
    mock_router.is_in_scope.return_value = (True, 0.89)

    agent = FiscalOrchestratorAgent(
        settings=Settings(),
        rfb_client=mock_rfb,
        cache_service=mock_cache,
        semantic_router=mock_router,
        openai_client=mock_llm,
    )

    res = await agent.process_message(
        "sess-2",
        "Simule curso de R$ 1000 no Regime Regular em SP para o CPF 123.456.789-00",
    )

    assert res.in_scope is True
    assert res.pii_redacted_count == 1
    assert len(res.tool_executions) == 1
    assert res.tool_executions[0]["tool"] == "simular_regime_regular"

    # Garante que o CPF nunca chegou na chamada ao LLM
    first_call_messages = mock_llm.chat.completions.create.call_args_list[0].kwargs[
        "messages"
    ]
    assert "123.456.789-00" not in json.dumps(first_call_messages)
    assert "[CPF_OCULTO]" in json.dumps(first_call_messages)
    assert (
        mock_llm.chat.completions.create.call_args_list[0].kwargs["max_tokens"]
        == 1024
    )
    mock_cache.save_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_limits_history_sent_to_llm() -> None:
    mock_llm = MagicMock()
    mock_llm.chat.completions.create = AsyncMock(
        return_value=_make_text_completion("Resposta")
    )
    mock_cache = AsyncMock()
    mock_cache.get_session.return_value = {
        "messages": [
            {"role": "user", "content": "antiga"},
            {"role": "assistant", "content": "resposta antiga"},
            {"role": "user", "content": "recente"},
        ]
    }

    agent = FiscalOrchestratorAgent(
        settings=Settings(max_history_messages=2),
        rfb_client=AsyncMock(),
        cache_service=mock_cache,
        semantic_router=MagicMock(),
        openai_client=mock_llm,
    )

    await agent.process_message("sess-3", "nova mensagem")

    messages = mock_llm.chat.completions.create.call_args.kwargs["messages"]
    assert [message.get("content") for message in messages[1:]] == [
        "recente",
        "nova mensagem",
    ]


@pytest.mark.asyncio
async def test_agent_stops_after_rfb_unavailable() -> None:
    tool_args = {
        "dhFatoGerador": "2027-03-10T10:00:00-03:00",
        "municipio": 3550308,
        "uf": "SP",
        "itens": [
            {
                "numero": 1,
                "nbs": "122011200",
                "cst": "200",
                "cClassTrib": "200028",
                "baseCalculo": 1000.0,
            }
        ],
    }
    mock_llm = MagicMock()
    mock_llm.chat.completions.create = AsyncMock(
        return_value=_make_tool_completion(
            "call_1", "simular_regime_regular", tool_args
        )
    )
    mock_rfb = AsyncMock()
    mock_rfb.calcular_regime_regular.side_effect = RFBUnavailableError("sensitive")
    mock_cache = AsyncMock()
    mock_cache.get_session.return_value = None
    mock_router = MagicMock()
    mock_router.is_in_scope.return_value = (True, 0.9)

    agent = FiscalOrchestratorAgent(
        settings=Settings(),
        rfb_client=mock_rfb,
        cache_service=mock_cache,
        semantic_router=mock_router,
        openai_client=mock_llm,
    )

    result = await agent.process_message("sess-4", "Simule esta operação.")

    assert result.reply == (
        "O motor da Receita Federal está temporariamente indisponível. "
        "Tente novamente mais tarde."
    )
    mock_llm.chat.completions.create.assert_awaited_once()
