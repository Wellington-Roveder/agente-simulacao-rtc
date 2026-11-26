from dataclasses import dataclass
from typing import Protocol

import numpy as np
from fastembed import TextEmbedding

from app.core.config import Settings

_DOMAIN_ANCHORS: tuple[str, ...] = (
    "simular imposto reforma tributária CBS IBS imposto seletivo",
    "calcular tributos venda de curso serviço produto nota fiscal",
    "alíquota simples nacional regime regular lucro presumido real",
    "gerar DANFSe XML nota fiscal de serviço eletrônica",
    "classificação tributária cClassTrib NBS NCM redução de alíquota",
)


class EmbeddingProvider(Protocol):
    """Contrato estrutural para permitir injeção de mock leve nos testes unitários."""

    def embed(self, documents: list[str]) -> list[np.ndarray]: ...


@dataclass(frozen=True)
class SemanticMatch:
    code: str
    description: str
    score: float
    metadata: dict[str, str]


class SemanticRouter:
    """
    Roteador semântico local baseado em embeddings densos (MiniLM-L12).
    Filtra consultas fora do domínio fiscal e mapeia descrições livres para códigos RFB.
    """

    def __init__(
        self,
        settings: Settings,
        embedder: EmbeddingProvider | None = None,
        scope_threshold: float = 0.35,
    ) -> None:
        self._model_name = settings.embedding_model_name
        self._embedder: EmbeddingProvider | None = embedder
        self._scope_threshold = scope_threshold
        self._anchor_matrix: np.ndarray | None = None

    def _get_embedder(self) -> EmbeddingProvider:
        if self._embedder is None:
            # Carregamento tardio (lazy) para não travar o import do módulo
            self._embedder = TextEmbedding(model_name=self._model_name)
        return self._embedder

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return vectors / norms

    def _encode(self, texts: list[str]) -> np.ndarray:
        raw = list(self._get_embedder().embed(texts))
        matrix = np.asarray(raw, dtype=np.float32)
        return self._normalize(matrix)

    def is_in_scope(self, query: str) -> tuple[bool, float]:
        """
        Verifica se a mensagem pertence ao domínio tributário da RTC.
        Retorna (dentro_do_escopo, maior_similaridade_cosseno).
        """
        cleaned = query.strip()
        if not cleaned:
            return False, 0.0

        if self._anchor_matrix is None:
            self._anchor_matrix = self._encode(list(_DOMAIN_ANCHORS))

        query_vec = self._encode([cleaned])[0]
        similarities = self._anchor_matrix @ query_vec
        best_score = float(np.max(similarities))
        return best_score >= self._scope_threshold, best_score

    def rank_catalog(
        self,
        query: str,
        catalog: list[dict[str, str]],
        top_k: int = 3,
    ) -> list[SemanticMatch]:
        """
        Ranqueia itens de um catálogo fiscal (ex.: NBS ou atividades SN)
        esperando chaves 'code' e 'description' em cada item.
        """
        if not catalog or not query.strip():
            return []

        descriptions = [item["description"] for item in catalog]
        doc_matrix = self._encode(descriptions)
        query_vec = self._encode([query.strip()])[0]

        scores = doc_matrix @ query_vec
        top_indices = np.argsort(scores)[::-1][:top_k]

        results: list[SemanticMatch] = []
        for idx in top_indices:
            item = catalog[int(idx)]
            extra = {k: v for k, v in item.items() if k not in {"code", "description"}}
            results.append(
                SemanticMatch(
                    code=item["code"],
                    description=item["description"],
                    score=float(scores[int(idx)]),
                    metadata=extra,
                )
            )
        return results
