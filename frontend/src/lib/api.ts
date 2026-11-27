const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export interface ToolExecutionSummary {
  tool: string;
  status: "ok" | "error";
}

export interface ChatResponse {
  reply: string;
  session_id: string;
  in_scope: boolean;
  pii_redacted_count: number;
  tools_used: ToolExecutionSummary[];
}

export interface DanfseGenerateResponse {
  download_token: string;
  download_url: string;
  expires_in_seconds: number;
}

export async function sendChatMessage(
  message: string,
  sessionId: string | null
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Erro na requisição." }));
    throw new Error(err.detail || `Erro HTTP ${response.status}`);
  }

  return response.json();
}

export async function generateDanfsePdf(
  xmlNfse: string,
  canhoto = true
): Promise<DanfseGenerateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/danfse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ xml_nfse: xmlNfse, canhoto }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Falha ao gerar DANFSe." }));
    throw new Error(err.detail || `Erro HTTP ${response.status}`);
  }

  return response.json();
}

export function getDanfseDownloadUrl(downloadPath: string): string {
  return `${API_BASE_URL}${downloadPath}`;
}