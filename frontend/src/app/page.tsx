"use client";

import { FormEvent, useState } from "react";
import {
  ChatResponse,
  generateDanfsePdf,
  getDanfseDownloadUrl,
  sendChatMessage,
  ToolExecutionSummary,
} from "@/lib/api";

interface MessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  piiRedacted?: number;
  inScope?: boolean;
  toolsUsed?: ToolExecutionSummary[];
}

const SAMPLE_PROMPTS = [
  "Simule uma venda de curso online (NBS 122011200, CST 200, cClassTrib 200028) de R$ 1.200,00 no Regime Regular em São Paulo/SP (IBGE 3550308) na data 2027-03-10.",
  "Quero simular uma prestação de serviço de R$ 850,00 no Simples Nacional (CRT 1, atividade 01, cClassTrib 000001) em 2027-03-15.",
  "Simule curso de R$ 500,00 no Regime Regular em SP para o CPF 123.456.789-00 e email cliente@teste.com.",
];

export default function HomePage() {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Estado do painel DANFSe
  const [xmlInput, setXmlInput] = useState("");
  const [danfseLoading, setDanfseLoading] = useState(false);
  const [danfseUrl, setDanfseUrl] = useState<string | null>(null);
  const [danfseError, setDanfseError] = useState<string | null>(null);

  async function handleSend(textToSend?: string) {
    const query = (textToSend ?? input).trim();
    if (!query || loading) return;

    setError(null);
    setInput("");
    const userMsg: MessageItem = {
      id: crypto.randomUUID(),
      role: "user",
      content: query,
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res: ChatResponse = await sendChatMessage(query, sessionId);
      setSessionId(res.session_id);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: res.reply,
          piiRedacted: res.pii_redacted_count,
          inScope: res.in_scope,
          toolsUsed: res.tools_used,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro inesperado ao consultar o agente.");
    } finally {
      setLoading(false);
    }
  }

  function handleFormSubmit(e: FormEvent) {
    e.preventDefault();
    void handleSend();
  }

  function handleResetSession() {
    setSessionId(null);
    setMessages([]);
    setError(null);
  }

  async function handleGenerateDanfse(e: FormEvent) {
    e.preventDefault();
    if (!xmlInput.trim() || danfseLoading) return;

    setDanfseError(null);
    setDanfseUrl(null);
    setDanfseLoading(true);

    try {
      const res = await generateDanfsePdf(xmlInput.trim(), true);
      setDanfseUrl(getDanfseDownloadUrl(res.download_url));
    } catch (err) {
      setDanfseError(err instanceof Error ? err.message : "Falha ao gerar PDF.");
    } finally {
      setDanfseLoading(false);
    }
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Cabeçalho + Aviso Legal */}
      <header className="border-b border-slate-800 bg-slate-900/80 px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-emerald-400">
              Agente de Simulação Tributária — RTC (LC 214/2025)
            </h1>
            <p className="text-xs text-slate-400">
              Orquestração Determinística • Motores Oficiais RFB (CBS, IBS, IS & DANFSe)
            </p>
          </div>
          <span className="inline-flex items-center rounded-md bg-amber-500/10 border border-amber-500/30 px-3 py-1 text-xs text-amber-300">
            Ambiente de Simulação — Sem validade jurídica ou fiscal
          </span>
        </div>
      </header>

      {/* Grid Principal */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Coluna Esquerda: Chat */}
        <section className="lg:col-span-7 flex flex-col bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300">
              Sessão Efêmera (Redis TTL):{" "}
              <code className="text-emerald-400">{sessionId ? sessionId.slice(0, 12) : "nova"}</code>
            </span>
            <button
              type="button"
              onClick={handleResetSession}
              className="text-xs text-slate-400 hover:text-slate-200 underline"
            >
              Nova simulação
            </button>
          </div>

          {/* Lista de Mensagens */}
          <div className="flex-1 p-4 space-y-4 overflow-y-auto max-h-[540px]">
            {messages.length === 0 && (
              <div className="space-y-3 py-6">
                <p className="text-sm text-slate-400">
                  Descreva uma operação comercial ou de serviço para simular CBS, IBS e Imposto
                  Seletivo, ou teste um dos cenários abaixo:
                </p>
                <div className="space-y-2">
                  {SAMPLE_PROMPTS.map((sample, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => void handleSend(sample)}
                      className="w-full text-left text-xs p-3 rounded-lg bg-slate-800/70 hover:bg-slate-800 border border-slate-700/70 text-slate-300 transition"
                    >
                      {sample}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${
                  msg.role === "user" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`max-w-[88%] rounded-xl px-4 py-3 text-sm whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "bg-emerald-600 text-white"
                      : "bg-slate-800 text-slate-100 border border-slate-700"
                  }`}
                >
                  {msg.content}
                </div>

                {msg.role === "assistant" && (
                  <div className="flex flex-wrap gap-2 mt-1.5 text-[11px]">
                    {typeof msg.piiRedacted === "number" && msg.piiRedacted > 0 && (
                      <span className="px-2 py-0.5 rounded bg-sky-500/15 text-sky-300 border border-sky-500/30">
                        LGPD: {msg.piiRedacted} dado(s) mascarado(s)
                      </span>
                    )}
                    {msg.inScope === false && (
                      <span className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30">
                        Bloqueado pelo Gatekeeper Semântico
                      </span>
                    )}
                    {msg.toolsUsed?.map((t, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                      >
                        Motor RFB: {t.tool} ({t.status})
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="text-xs text-slate-400 animate-pulse">
                Consultando orquestrador e motores da Receita Federal...
              </div>
            )}

            {error && (
              <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-700 text-xs text-rose-200">
                {error}
              </div>
            )}
          </div>

          {/* Formulário de Envio */}
          <form onSubmit={handleFormSubmit} className="p-3 border-t border-slate-800 flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ex: Simule venda de mentoria de R$ 1.500 no Simples Nacional..."
              className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-sm font-medium text-white transition"
            >
              Simular
            </button>
          </form>
        </section>

        {/* Coluna Direita: Telemetria & Gerador DANFSe */}
        <aside className="lg:col-span-5 space-y-6">
          {/* Card de Auditoria */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <h2 className="text-sm font-semibold text-slate-200">
              Auditoria da Última Resposta
            </h2>
            {lastAssistant ? (
              <dl className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <dt className="text-slate-400">Escopo Tributário</dt>
                  <dd className="mt-1 font-medium text-emerald-400">
                    {lastAssistant.inScope ? "Validado (MiniLM-L12)" : "Fora de Escopo"}
                  </dd>
                </div>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <dt className="text-slate-400">PII Mascarado (LGPD)</dt>
                  <dd className="mt-1 font-medium text-sky-400">
                    {lastAssistant.piiRedacted ?? 0} ocorrência(s)
                  </dd>
                </div>
                <div className="col-span-2 bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <dt className="text-slate-400">Motores RFB Acionados</dt>
                  <dd className="mt-1 font-mono text-slate-200">
                    {lastAssistant.toolsUsed && lastAssistant.toolsUsed.length > 0
                      ? lastAssistant.toolsUsed.map((t) => `${t.tool} [${t.status}]`).join(", ")
                      : "Nenhum cálculo executado nesta rodada"}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="text-xs text-slate-400">
                Envie uma simulação no chat para inspecionar o roteamento semântico, a
                anonimização LGPD e as chamadas aos contêineres da Receita Federal.
              </p>
            )}
          </div>

          {/* Card Gerador DANFSe (Motor Go) */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-200">
                Prévia de DANFSe (Motor Oficial Go)
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Cole o XML de uma NFS-e para renderizar o PDF temporário via{" "}
                <code>calculadora-rtc-gerador-danfse</code>.
              </p>
            </div>

            <form onSubmit={handleGenerateDanfse} className="space-y-3">
              <textarea
                rows={5}
                value={xmlInput}
                onChange={(e) => setXmlInput(e.target.value)}
                placeholder="<NFSe>...</NFSe>"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={danfseLoading || !xmlInput.trim()}
                className="w-full py-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 border border-slate-700 text-xs font-medium text-slate-100 transition"
              >
                {danfseLoading ? "Renderizando PDF..." : "Gerar PDF DANFSe"}
              </button>
            </form>

            {danfseError && (
              <p className="text-xs text-rose-300 bg-rose-950/50 border border-rose-800 rounded p-2">
                {danfseError}
              </p>
            )}

            {danfseUrl && (
              <a
                href={danfseUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="block text-center py-2 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/40 text-xs font-medium text-emerald-300"
              >
                Baixar PDF Gerado (expira em 10 min)
              </a>
            )}
          </div>
        </aside>
      </main>
    </div>
  );
}