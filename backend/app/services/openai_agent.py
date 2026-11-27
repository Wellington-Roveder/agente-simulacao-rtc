import json
import logging
from dataclasses import dataclass, field
from typing import Any

from openai import APIError, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from app.core.config import Settings
from app.core.errors import (
    LLMProviderError,
    RFBUnavailableError,
    RFBValidationError,
)
from app.core.security import sanitize_pii
from app.schemas.fiscal import OperacaoRegimeGeralInput, OperacaoSimplesInput
from app.services.cache_service import CacheService
from app.services.rfb_client import RFBFiscalClient
from app.services.semantic_router import SemanticRouter

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """
Você é um assistente especialista na Reforma Tributária do Consumo do Brasil (LC 214/2025: CBS, IBS e Imposto Seletivo).
REGRAS ESTRITAS:
1. NUNCA calcule tributos, alíquotas ou valores por conta própria. Sempre utilize as ferramentas oficiais disponíveis.
2. Se faltarem dados obrigatórios para a simulação (ex.: regime tributário, valor da operação, município/UF no Regime Regular, ou data/cClassTrib no Simples Nacional), peça ao usuário de forma objetiva antes de chamar a calculadora.
3. Ao apresentar o resultado, destaque os valores oficiais retornados pelo motor da Receita Federal e alerte caso algum item retorne estado INCONSISTENCIA_ENTRADA ou NAO_CALCULADO. 
4. Lembre sempre que os números têm caráter exclusivamente simulatório.
""".strip()  # noqa: E501

_OFF_TOPIC_REPLY = (
    "Sou um simulador especializado exclusivamente na Reforma Tributária do Consumo "
    "(CBS, IBS e Imposto Seletivo — LC 214/2025). Envie os dados de uma operação "
    "comercial ou prestação de serviço para simular os tributos."
)

_TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "simular_regime_regular",
            "description": (
                "Calcula CBS, IBS e Imposto Seletivo no Regime Regular (Lucro Real ou Presumido) "  # noqa: E501
                "usando o motor oficial da Receita Federal."
            ),
            "parameters": OperacaoRegimeGeralInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simular_simples_nacional",
            "description": (
                "Calcula CBS e IBS para optantes do Simples Nacional (NT 2026.005) "
                "usando o motor oficial da Receita Federal."
            ),
            "parameters": OperacaoSimplesInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_atividades_simples",
            "description": (
                "Consulta o catálogo oficial de atividades vigentes do Simples Nacional "  # noqa: E501
                "em uma data específica (YYYY-MM-DD) para identificar códigos cAtivSN e anexos."  # noqa: E501
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data_vigencia": {
                        "type": "string",
                        "description": "Data no formato YYYY-MM-DD (ex: 2027-03-15)",
                    }
                },
                "required": ["data_vigencia"],
            },
        },
    },
]


@dataclass
class AgentResponse:
    reply: str
    session_id: str
    in_scope: bool
    pii_redacted_count: int = 0
    tool_executions: list[dict[str, Any]] = field(default_factory=list)


class FiscalOrchestratorAgent:
    """
    Orquestrador conversacional que combina filtro LGPD, roteamento semântico local
    e Tool Calling determinístico contra os motores da Receita Federal.
    """

    def __init__(
        self,
        settings: Settings,
        rfb_client: RFBFiscalClient,
        cache_service: CacheService,
        semantic_router: SemanticRouter,
        openai_client: AsyncOpenAI | None = None,
        max_tool_rounds: int = 4,
    ) -> None:
        self._model = settings.llm_model
        self._max_history_messages = settings.max_history_messages
        self._rfb = rfb_client
        self._cache = cache_service
        self._router = semantic_router
        self._llm = openai_client or AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_base_url,
            timeout=settings.llm_timeout_seconds,
        )
        self._max_tool_rounds = max_tool_rounds

    async def process_message(
        self, session_id: str, user_message: str
    ) -> AgentResponse:
        # 1. Privacidade by Design: mascara PII antes de qualquer processamento externo
        sanitized = sanitize_pii(user_message)
        clean_text = sanitized.sanitized_text

        # 2. Recupera histórico efêmero no Redis
        session_state = await self._cache.get_session(session_id) or {"messages": []}
        history: list[ChatCompletionMessageParam] = session_state["messages"]

        # 3. Gatekeeper Semântico Local: se não há histórico ativo, valida escopo antes do LLM # noqa: E501
        if not history:
            in_scope, _ = self._router.is_in_scope(clean_text)
            if not in_scope:
                return AgentResponse(
                    reply=_OFF_TOPIC_REPLY,
                    session_id=session_id,
                    in_scope=False,
                    pii_redacted_count=sanitized.redacted_count,
                )

        history.append({"role": "user", "content": clean_text})
        tool_executions: list[dict[str, Any]] = []

        # 4. Loop determinístico de Tool Calling
        for _ in range(self._max_tool_rounds):
            messages: list[ChatCompletionMessageParam] = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                *history[-self._max_history_messages :],
            ]
            try:
                completion = await self._llm.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=_TOOLS,
                    tool_choice="auto",
                    temperature=0.0,
                    max_tokens=1024,
                )
            except APIError as exc:
                logger.warning(
                    "Erro na chamada ao provedor LLM: %s - %s | Causa: %r",
                    type(exc).__name__,
                    exc,
                    exc.__cause__,
                )  # noqa: E501
                raise LLMProviderError("Falha na API do modelo de linguagem.") from exc
            assistant_msg = completion.choices[0].message

            if not assistant_msg.tool_calls:
                final_text = assistant_msg.content or ""
                history.append({"role": "assistant", "content": final_text})
                await self._cache.save_session(session_id, {"messages": history})
                return AgentResponse(
                    reply=final_text,
                    session_id=session_id,
                    in_scope=True,
                    pii_redacted_count=sanitized.redacted_count,
                    tool_executions=tool_executions,
                )

            # Registra a intenção de chamada de ferramenta no histórico
            history.append(assistant_msg.model_dump(exclude_none=True))  # type: ignore[arg-type]

            for tool_call in assistant_msg.tool_calls:
                fn_name = tool_call.function.name
                raw_args = tool_call.function.arguments
                try:
                    tool_output = await self._execute_tool(fn_name, raw_args)
                except RFBUnavailableError:
                    tool_executions.append(
                        {
                            "tool": fn_name,
                            "output": {"erro_execucao": "Motor da RFB indisponível."},
                        }
                    )
                    return AgentResponse(
                        reply=(
                            "O motor da Receita Federal está temporariamente "
                            "indisponível. Tente novamente mais tarde."
                        ),
                        session_id=session_id,
                        in_scope=True,
                        pii_redacted_count=sanitized.redacted_count,
                        tool_executions=tool_executions,
                    )
                tool_executions.append({"tool": fn_name, "output": tool_output})

                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_output, ensure_ascii=False),
                    }
                )

        fallback = (
            "Não foi possível concluir a orquestração dentro do limite de etapas. "
            "Tente simplificar os itens da operação."
        )
        return AgentResponse(
            reply=fallback,
            session_id=session_id,
            in_scope=True,
            pii_redacted_count=sanitized.redacted_count,
            tool_executions=tool_executions,
        )

    async def _execute_tool(self, fn_name: str, raw_arguments: str) -> dict[str, Any]:
        try:
            args = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            return {"erro": f"Argumentos JSON inválidos gerados pelo modelo: {exc}"}

        try:
            if fn_name == "simular_regime_regular":
                payload = OperacaoRegimeGeralInput.model_validate(args)
                result = await self._rfb.calcular_regime_regular(payload)
                return result.model_dump(mode="json")

            if fn_name == "simular_simples_nacional":
                payload_sn = OperacaoSimplesInput.model_validate(args)
                result_sn = await self._rfb.calcular_simples_nacional(payload_sn)
                return result_sn.model_dump(mode="json")

            if fn_name == "consultar_atividades_simples":
                data_vigencia = str(args.get("data_vigencia", ""))
                cache_key = f"atividades_sn:{data_vigencia}"
                cached = await self._cache.get_fiscal_table(cache_key)
                if cached is not None:
                    return {"fonte": "cache_redis", "atividades": cached[:20]}

                atividades = await self._rfb.listar_atividades_simples(data_vigencia)
                await self._cache.set_fiscal_table(cache_key, atividades)
                return {"fonte": "rfb_api", "atividades": atividades[:20]}

            return {"erro": f"Ferramenta desconhecida: {fn_name}"}
        except (ValueError, RFBValidationError) as exc:
            return {"erro_execucao": str(exc)}
