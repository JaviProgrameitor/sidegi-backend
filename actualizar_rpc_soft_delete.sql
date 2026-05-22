-- ====================================================================
-- ACTUALIZACIÓN DE BÚSQUEDA VECTORIAL CON SOFT DELETE - SIGEDI
-- ====================================================================
-- Este script actualiza la función RPC buscar_fragmentos_similares
-- para ignorar documentos o carpetas marcados como eliminados (esta_eliminado = 1)
-- ====================================================================

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
  LEFT JOIN public.folders f ON di.carpeta_id = f.id_folder
  WHERE di.usuario_id = usuario_id_filtro
    AND (carpeta_id_filtro IS NULL OR di.carpeta_id = carpeta_id_filtro)
    AND (di.esta_eliminado IS NULL OR di.esta_eliminado != 1)
    AND (f.esta_eliminado IS NULL OR f.esta_eliminado != 1)
  ORDER BY de.embedding <=> consulta_embedding
  LIMIT limite;
END;
$$;
