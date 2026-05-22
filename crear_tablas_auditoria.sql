-- Creación de la tabla de auditoría de documentos para SIGEDI
CREATE TABLE IF NOT EXISTS public.documentos_auditoria (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    documento_id UUID NOT NULL,
    hallazgos JSONB NOT NULL,
    nivel_riesgo VARCHAR(20) CHECK (nivel_riesgo IN ('bajo', 'medio', 'alto', 'critico')),
    hash_reporte VARCHAR(64) NOT NULL,
    generado_en TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT fk_auditoria_documento FOREIGN KEY (documento_id) REFERENCES public.documentos_integridad(id) ON DELETE CASCADE
);
