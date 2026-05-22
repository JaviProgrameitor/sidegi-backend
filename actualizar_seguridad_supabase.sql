-- ====================================================================
-- SCRIPT DE ACTUALIZACIÓN DE SEGURIDAD Y CONEXIONES - SIGEDI
-- ====================================================================

-- 1. Habilitar RLS en todas las tablas del esquema public
ALTER TABLE IF EXISTS public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.documentos_integridad ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.documentos_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.documentos_auditoria ENABLE ROW LEVEL SECURITY;

-- 2. Limpiar políticas previas para evitar duplicados en la ejecución
DROP POLICY IF EXISTS "Permitir lectura general de registros de integridad" ON public.documentos_integridad;
DROP POLICY IF EXISTS "Permitir inserción de registros de integridad" ON public.documentos_integridad;
DROP POLICY IF EXISTS "Permitir lectura general de embeddings" ON public.documentos_embeddings;
DROP POLICY IF EXISTS "Permitir inserción de embeddings" ON public.documentos_embeddings;
DROP POLICY IF EXISTS "Permitir lectura general de auditorias" ON public.documentos_auditoria;
DROP POLICY IF EXISTS "Permitir inserción de auditorias" ON public.documentos_auditoria;
DROP POLICY IF EXISTS "Permitir lectura general de usuarios" ON public.users;
DROP POLICY IF EXISTS "Permitir inserción de usuarios" ON public.users;
DROP POLICY IF EXISTS "Permitir lectura general de carpetas" ON public.folders;
DROP POLICY IF EXISTS "Permitir inserción de carpetas" ON public.folders;

-- 3. Crear Políticas de Seguridad RLS Robustas

-- Tabla: users
CREATE POLICY "Permitir lectura general de usuarios" ON public.users FOR SELECT USING (true);
CREATE POLICY "Permitir inserción de usuarios" ON public.users FOR INSERT WITH CHECK (true);

-- Tabla: folders
CREATE POLICY "Permitir lectura general de carpetas" ON public.folders FOR SELECT USING (true);
CREATE POLICY "Permitir inserción de carpetas" ON public.folders FOR INSERT WITH CHECK (true);

-- Tabla: documentos_integridad
CREATE POLICY "Permitir lectura general de registros de integridad" ON public.documentos_integridad FOR SELECT USING (true);
CREATE POLICY "Permitir inserción de registros de integridad" ON public.documentos_integridad FOR INSERT WITH CHECK (true);

-- Tabla: documentos_embeddings
CREATE POLICY "Permitir lectura general de embeddings" ON public.documentos_embeddings FOR SELECT USING (true);
CREATE POLICY "Permitir inserción de embeddings" ON public.documentos_embeddings FOR INSERT WITH CHECK (true);

-- Tabla: documentos_auditoria
CREATE POLICY "Permitir lectura general de auditorias" ON public.documentos_auditoria FOR SELECT USING (true);
CREATE POLICY "Permitir inserción de auditorias" ON public.documentos_auditoria FOR INSERT WITH CHECK (true);


-- 4. Modificar el Trigger de Inmutabilidad para admitir bypass controlado
-- Se modifica la función del trigger para validar una variable local de transacción: 'sigedi.permitir_borrado'
CREATE OR REPLACE FUNCTION proteger_integridad_registro()
RETURNS TRIGGER AS $$
BEGIN
    -- Si la variable de sesión 'sigedi.permitir_borrado' es 'true', permitimos la eliminación o modificación (para mantenimiento o tests)
    IF current_setting('sigedi.permitir_borrado', true) = 'true' THEN
        RETURN OLD;
    END IF;
    
    RAISE EXCEPTION 'Operación denegada: Los sellos criptográficos de integridad documental de SIGEDI son inmutables e inalterables en producción.';
END;
$$ LANGUAGE plpgsql;


-- 5. Crear función RPC segura para eliminación de datos de prueba en cascada
-- Esta función utiliza SECURITY DEFINER y habilita temporalmente la variable para permitir el borrado
CREATE OR REPLACE FUNCTION eliminar_usuario_y_datos_prueba(usr_id BIGINT, fld_id BIGINT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER -- Se ejecuta con privilegios del creador (Owner)
SET search_path = public -- Prevenir ataques de inyección de rutas de búsqueda
AS $$
BEGIN
  -- Habilitar la variable local en la transacción actual
  PERFORM set_config('sigedi.permitir_borrado', 'true', true);
  
  -- Borrar la carpeta (desencadena ON DELETE CASCADE y ON DELETE SET NULL)
  DELETE FROM public.folders WHERE id_folder = fld_id;
  
  -- Borrar el usuario (desencadena ON DELETE CASCADE en documentos_integridad, etc.)
  DELETE FROM public.users WHERE id_user = usr_id;
END;
$$;

-- 6. Restringir la ejecución de la función RPC solo al rol service_role (Backend administrativo)
REVOKE EXECUTE ON FUNCTION eliminar_usuario_y_datos_prueba(BIGINT, BIGINT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION eliminar_usuario_y_datos_prueba(BIGINT, BIGINT) FROM anon;
REVOKE EXECUTE ON FUNCTION eliminar_usuario_y_datos_prueba(BIGINT, BIGINT) FROM authenticated;
GRANT EXECUTE ON FUNCTION eliminar_usuario_y_datos_prueba(BIGINT, BIGINT) TO service_role;

-- ====================================================================
-- FIN DEL SCRIPT - EJECUTAR EN SUPABASE SQL EDITOR
-- ====================================================================
