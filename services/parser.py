import markdown

def parsear_markdown_a_html(texto_markdown: str) -> str:
    """
    Convierte una cadena de texto en formato Markdown a HTML estructurado.
    
    Habilita extensiones comunes para soportar tablas, bloques de código cercados
    y saltos de línea inteligentes de forma segura.
    
    Args:
        texto_markdown (str): El texto original en Markdown generado por la IA.
        
    Returns:
        str: El texto formateado en HTML.
    """
    if not texto_markdown:
        return ""
        
    # Extensiones de Markdown estándar y útiles para la interfaz
    extensiones = [
        "fenced_code",  # Bloques de código con ```
        "tables",       # Tablas de Markdown estilo GitHub
        "nl2br",        # Convierte saltos de línea sencillos en etiquetas <br>
        "sane_lists"    # Renderiza listas de manera consistente y sin anidación errónea
    ]
    
    try:
        return markdown.markdown(texto_markdown, extensions=extensiones)
    except Exception as e:
        print(f"Error al parsear Markdown a HTML: {e}")
        # Retornamos el texto original como fallback en caso de error
        return texto_markdown
