-- ====================================================================
-- SCRIPT DE MIGRACIÓN VECTORIAL (RAG) - SIGEDI_DB
-- ====================================================================
-- Este script habilita la extensión pgvector en Supabase, crea la tabla de
-- embeddings y registra la función RPC para búsqueda semántica por coseno.
-- ====================================================================

-- 1. Habilitar extensión vectorial pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Tabla de fragmentos vectorizados (Embeddings de 1536 dimensiones)
-- Está referenciada directamente a la tabla inmutable de integridad public.documentos_integridad
CREATE TABLE IF NOT EXISTS public.documentos_embeddings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,            -- ID único del fragmento
    documento_id UUID NOT NULL,                               -- Referencia FK al documento en documentos_integridad
    fragmento TEXT NOT NULL,                                  -- Texto plano del fragmento
    embedding vector(1536),                                   -- Vector generado (1536 dimensiones para Cohere embed-v4.0)
    posicion INT DEFAULT 0,                                   -- Posición ordinal del fragmento en el documento
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,

    -- Borrado seguro en cascada al eliminar el documento de la tabla principal
    CONSTRAINT fk_embeddings_documento FOREIGN KEY (documento_id) REFERENCES public.documentos_integridad(id) ON DELETE CASCADE
);

-- 3. Crear índice de búsqueda rápida utilizando coseno (IVFFlat)
CREATE INDEX IF NOT EXISTS idx_documentos_embeddings_vector 
ON public.documentos_embeddings 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- 4. Función RPC en Postgres para realizar búsqueda semántica por similitud de coseno
-- Retorna el ID del fragmento, el documento asociado, el texto del fragmento y su similitud (0.0 a 1.0)
CREATE OR REPLACE FUNCTION public.buscar_fragmentos_similares(
  consulta_embedding vector(1536),
  usuario_id_filtro BIGINT,
  carpeta_id_filtro BIGINT DEFAULT NULL,
  limite INT DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  documento_id UUID,
  fragmento TEXT,
  similitud FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    de.id,
    de.documento_id,
    de.fragmento,
    (1 - (de.embedding <=> consulta_embedding))::FLOAT AS similitud
  FROM public.documentos_embeddings de
  INNER JOIN public.documentos_integridad di ON de.documento_id = di.id
  WHERE di.usuario_id = usuario_id_filtro
    AND (carpeta_id_filtro IS NULL OR di.carpeta_id = carpeta_id_filtro)
  ORDER BY de.embedding <=> consulta_embedding
  LIMIT limite;
END;
$$;

-- ====================================================================
-- FIN DEL SCRIPT DE INDEXACIÓN - EJECUTAR EN SQL EDITOR DE SUPABASE
-- ====================================================================
