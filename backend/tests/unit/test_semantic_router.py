import numpy as np

from app.core.config import Settings
from app.services.semantic_router import SemanticRouter


class FakeEmbedder:
    """Embedder determinístico em 3 eixos: [tributos/educação, culinária, software]."""

    def embed(self, documents: list[str]) -> list[np.ndarray]:
        vectors: list[np.ndarray] = []
        for doc in documents:
            lower = doc.lower()
            if any(
                w in lower
                for w in (
                    "imposto",
                    "cbs",
                    "ibs",
                    "tribut",
                    "curso",
                    "educação",
                    "danfse",
                )
            ):
                vectors.append(np.array([1.0, 0.0, 0.0], dtype=np.float32))
            elif any(w in lower for w in ("bolo", "receita culinária", "chocolate")):
                vectors.append(np.array([0.0, 1.0, 0.0], dtype=np.float32))
            else:
                vectors.append(np.array([0.0, 0.0, 1.0], dtype=np.float32))
        return vectors


def test_is_in_scope_accepts_fiscal_query_and_rejects_offtopic() -> None:
    router = SemanticRouter(
        settings=Settings(),
        embedder=FakeEmbedder(),
        scope_threshold=0.5,
    )

    in_scope, score_ok = router.is_in_scope(
        "Quero simular CBS e IBS de um curso online"
    )
    off_topic, score_bad = router.is_in_scope(
        "Me dê uma receita culinária de bolo de chocolate"
    )

    assert in_scope is True
    assert score_ok >= 0.99
    assert off_topic is False
    assert score_bad == 0.0


def test_rank_catalog_returns_best_fiscal_match_first() -> None:
    router = SemanticRouter(settings=Settings(), embedder=FakeEmbedder())
    catalog = [
        {"code": "999999", "description": "Receita culinária artesanal", "cst": "000"},
        {
            "code": "122011200",
            "description": "Serviços de educação e ensino",
            "cst": "200",
        },
    ]

    matches = router.rank_catalog("Simular venda de curso gravado", catalog, top_k=2)

    assert len(matches) == 2
    assert matches[0].code == "122011200"
    assert matches[0].metadata["cst"] == "200"
    assert matches[0].score > matches[1].score
