
from sentence_transformers import SentenceTransformer

_model = None


def get_embedder() -> SentenceTransformer:
    """Singleton para no cargar el modelo múltiples veces."""
    global _model
    if _model is None:
        _model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
    return _model