import os
import random
from typing import Union

try:
    import cohere
    COHERE_DISPONIBLE = True
except ImportError:
    cohere = None
    COHERE_DISPONIBLE = False


class MockEmbedder:
    """Mock para generar embeddings de prueba de 1536 dimensiones si Cohere no está disponible."""
    def __init__(self):
        self.dimension = 1536

    def encode(self, texto: str) -> list[float]:
        # Generar un vector determinista basado en el hash del texto
        random.seed(hash(texto))
        vector = [random.uniform(-0.1, 0.1) for _ in range(self.dimension)]
        # Normalizar para similitud de coseno
        norma = sum(x * x for x in vector) ** 0.5
        return [x / norma for x in vector] if norma > 0 else vector

    def encode_query(self, query: str) -> list[float]:
        return self.encode(query)


class CohereEmbedder:
    """Generador de embeddings utilizando Cohere embed-v4.0 (1536 dimensiones)."""
    def __init__(self, api_key: str):
        if not COHERE_DISPONIBLE:
            raise ImportError("La librería 'cohere' no está instalada.")
        self.client = cohere.ClientV2(api_key=api_key)
        self.dimension = 1536

    def encode(self, texto: str) -> list[float]:
        try:
            respuesta = self.client.embed(
                texts=[texto],
                model="embed-v4.0",
                input_type="search_document",
                embedding_types=["float"]
            )
            return respuesta.embeddings.float_[0]
        except Exception as e:
            print(f"Error al generar embedding con Cohere (document): {e}. Usando fallback mock.")
            return MockEmbedder().encode(texto)

    def encode_query(self, query: str) -> list[float]:
        try:
            respuesta = self.client.embed(
                texts=[query],
                model="embed-v4.0",
                input_type="search_query",
                embedding_types=["float"]
            )
            return respuesta.embeddings.float_[0]
        except Exception as e:
            print(f"Error al generar embedding con Cohere (query): {e}. Usando fallback mock.")
            return MockEmbedder().encode_query(query)


_embedder = None

def get_embedder() -> Union[CohereEmbedder, MockEmbedder]:
    """Singleton para obtener el generador de embeddings (Cohere o Mock)."""
    global _embedder
    if _embedder is None:
        clave_cohere = os.environ.get("COHERE_API_KEY", "")
        if clave_cohere and COHERE_DISPONIBLE:
            try:
                print("Iniciando servicio de embeddings real con Cohere...")
                _embedder = CohereEmbedder(clave_cohere)
            except Exception as e:
                print(f"Advertencia: No se pudo iniciar CohereEmbedder: {e}. Usando MockEmbedder.")
                _embedder = MockEmbedder()
        else:
            if not COHERE_DISPONIBLE:
                print("Aviso: Librería 'cohere' no disponible en el entorno virtual. Usando MockEmbedder.")
            else:
                print("Aviso: COHERE_API_KEY no configurada en el entorno. Usando MockEmbedder.")
            _embedder = MockEmbedder()
    return _embedder