-- ====================================================================
-- SCRIPT DE INTEGRIDAD DOCUMENTAL Y AUDITORÍA - SIGEDI_DB
-- ====================================================================
-- Este script crea la tabla de integridad documental, optimiza sus índices,
-- habilita seguridad Row Level Security (RLS) y establece restricciones de
-- inmutabilidad mediante un trigger para auditoría forense.
-- ====================================================================

-- 1. Creación de la Tabla public.documentos_integridad
CREATE TABLE IF NOT EXISTS public.documentos_integridad (
    id UUID PRIMARY KEY,                                      -- ID único del documento (UUID v4 generado por el backend)
    nombre TEXT NOT NULL,                                     -- Nombre del archivo físico
    ruta_archivo TEXT NOT NULL,                               -- Ruta física de almacenamiento
    hash_sha256 VARCHAR(64) NOT NULL,                         -- Firma criptográfica del documento (SHA-256)
    usuario_id BIGINT NOT NULL,                               -- Referencia al usuario dueño (public.users.id_user)
    carpeta_id BIGINT NULL,                                   -- Referencia a la carpeta contenedora (public.folders.id_folder)
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,

    -- Restricciones de integridad referencial con borrado seguro
    CONSTRAINT fk_integridad_usuario FOREIGN KEY (usuario_id) REFERENCES public.users(id_user) ON DELETE CASCADE,
    CONSTRAINT fk_integridad_carpeta FOREIGN KEY (carpeta_id) REFERENCES public.folders(id_folder) ON DELETE SET NULL
);

-- 2. Creación de Índices para Optimización de Consultas O(log N)
-- Índice único de búsqueda criptográfica rápido por hash del archivo
CREATE UNIQUE INDEX IF NOT EXISTS idx_documentos_hash_unico ON public.documentos_integridad (hash_sha256);

-- Índices de búsqueda para optimizar consultas de los usuarios y jerarquía de carpetas
CREATE INDEX IF NOT EXISTS idx_documentos_usuario ON public.documentos_integridad (usuario_id);
CREATE INDEX IF NOT EXISTS idx_documentos_carpeta ON public.documentos_integridad (carpeta_id);

-- 3. Habilitar Seguridad Row Level Security (RLS)
ALTER TABLE public.documentos_integridad ENABLE ROW LEVEL SECURITY;

-- Política de lectura: Permitir lectura pública/autenticada para auditoría de integridad
CREATE POLICY "Permitir lectura general de registros de integridad" 
ON public.documentos_integridad
FOR SELECT 
USING (true);

-- Política de inserción: Permitir registrar nuevos sellos de integridad
CREATE POLICY "Permitir inserción de registros de integridad" 
ON public.documentos_integridad
FOR INSERT 
WITH CHECK (true);

-- 4. Establecer Sello de Inmutabilidad Criptográfica (Trigger Forense)
-- Función para bloquear cualquier modificación (UPDATE) o eliminación (DELETE) de sellos ya registrados
CREATE OR REPLACE FUNCTION proteger_integridad_registro()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Operación denegada: Los sellos criptográficos de integridad documental de SIGEDI son inmutables e inalterables.';
END;
$$ LANGUAGE plpgsql;

-- Trigger aplicado antes de actualizar o eliminar
CREATE TRIGGER trg_bloquear_modificacion_documentos
BEFORE UPDATE OR DELETE ON public.documentos_integridad
FOR EACH ROW
EXECUTE FUNCTION proteger_integridad_registro();

-- ====================================================================
-- FIN DEL SCRIPT DE INTEGRIDAD - EJECUTAR EN SQL EDITOR DE SUPABASE
-- ====================================================================
