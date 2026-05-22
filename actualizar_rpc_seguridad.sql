-- ====================================================================
-- ACTUALIZACIÓN DE SEGURIDAD PARA BÚSQUEDA SEMÁNTICA (RPC)
-- ====================================================================
-- Este script actualiza la función RPC buscar_fragmentos_similares
-- para aplicar aislamiento multiusuario (multi-tenancy) y evitar la fuga 
-- de datos. Ahora se filtran los fragmentos uniendo la tabla de embeddings
-- con la tabla de integridad documental por el ID del usuario y carpeta.
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
  WHERE di.usuario_id = usuario_id_filtro
    AND (carpeta_id_filtro IS NULL OR di.carpeta_id = carpeta_id_filtro)
  ORDER BY de.embedding <=> consulta_embedding
  LIMIT limite;
END;
$$;

-- Otorgar permisos de ejecución para roles autenticados y anónimos de PostgREST
GRANT EXECUTE ON FUNCTION public.buscar_fragmentos_similares(vector(1536), BIGINT, BIGINT, INT) TO anon;
GRANT EXECUTE ON FUNCTION public.buscar_fragmentos_similares(vector(1536), BIGINT, BIGINT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.buscar_fragmentos_similares(vector(1536), BIGINT, BIGINT, INT) TO service_role;
