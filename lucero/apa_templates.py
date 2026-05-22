"""
apa_templates.py — Plantillas XML para estructuras APA 7ª edición.
Cada función devuelve un fragmento OOXML listo para inyectar con lxml.
"""

from __future__ import annotations

from lxml import etree

from .utils import NS, get_logger

log = get_logger("aldradoc.apa")

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────────────────────────────────────

def _w(tag: str) -> str:
    return f"{{{NS['w']}}}{tag}"


def _make_run(text: str, bold: bool = False, italic: bool = False,
              font_size_half: int = 24) -> etree._Element:
    """Crea un <w:r> con formato básico."""
    run = etree.Element(_w("r"))
    rpr = etree.SubElement(run, _w("rPr"))
    if bold:
        etree.SubElement(rpr, _w("b"))
    if italic:
        etree.SubElement(rpr, _w("i"))
    sz = etree.SubElement(rpr, _w("sz"))
    sz.set(_w("val"), str(font_size_half))
    sz_cs = etree.SubElement(rpr, _w("szCs"))
    sz_cs.set(_w("val"), str(font_size_half))
    t = etree.SubElement(run, _w("t"))
    t.text = text
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return run


def _make_para(style_id: str, indent_left: int = 0,
               hanging: int = 0) -> etree._Element:
    """Crea un <w:p> con estilo y sangría configurados."""
    para = etree.Element(_w("p"))
    ppr = etree.SubElement(para, _w("pPr"))
    ps = etree.SubElement(ppr, _w("pStyle"))
    ps.set(_w("val"), style_id)
    if indent_left or hanging:
        ind = etree.SubElement(ppr, _w("ind"))
        if indent_left:
            ind.set(_w("left"), str(indent_left))
        if hanging:
            ind.set(_w("hanging"), str(hanging))
    return para


# ─────────────────────────────────────────────────────────────────────────────
# PLANTILLAS APA 7ª
# ─────────────────────────────────────────────────────────────────────────────

def apa_heading1(text: str) -> etree._Element:
    """
    Encabezado Nivel 1 APA 7ª:
    Centrado, negrita, sin cursiva, Title Case.
    """
    para = etree.Element(_w("p"))
    ppr = etree.SubElement(para, _w("pPr"))
    ps = etree.SubElement(ppr, _w("pStyle"))
    ps.set(_w("val"), "Heading1")
    jc = etree.SubElement(ppr, _w("jc"))
    jc.set(_w("val"), "center")
    para.append(_make_run(text, bold=True))
    log.debug("apa_heading1 generado: %r", text)
    return para


def apa_heading2(text: str) -> etree._Element:
    """
    Encabezado Nivel 2 APA 7ª:
    Alineado a la izquierda, negrita, sin cursiva.
    """
    para = etree.Element(_w("p"))
    ppr = etree.SubElement(para, _w("pPr"))
    ps = etree.SubElement(ppr, _w("pStyle"))
    ps.set(_w("val"), "Heading2")
    para.append(_make_run(text, bold=True))
    log.debug("apa_heading2 generado: %r", text)
    return para


def apa_heading3(text: str) -> etree._Element:
    """
    Encabezado Nivel 3 APA 7ª:
    Alineado a la izquierda, negrita, cursiva.
    """
    para = etree.Element(_w("p"))
    ppr = etree.SubElement(para, _w("pPr"))
    ps = etree.SubElement(ppr, _w("pStyle"))
    ps.set(_w("val"), "Heading3")
    para.append(_make_run(text, bold=True, italic=True))
    log.debug("apa_heading3 generado: %r", text)
    return para


def apa_body_paragraph(text: str, first_line_indent: int = 720) -> etree._Element:
    """
    Párrafo de cuerpo APA 7ª:
    Sangría de primera línea 1.27 cm (720 twips), justificado, Times New Roman 12pt.
    """
    para = etree.Element(_w("p"))
    ppr = etree.SubElement(para, _w("pPr"))
    ps = etree.SubElement(ppr, _w("pStyle"))
    ps.set(_w("val"), "Normal")
    ind = etree.SubElement(ppr, _w("ind"))
    ind.set(_w("firstLine"), str(first_line_indent))
    jc = etree.SubElement(ppr, _w("jc"))
    jc.set(_w("val"), "both")
    spacing = etree.SubElement(ppr, _w("spacing"))
    spacing.set(_w("line"), "480")       # Doble espacio = 24pt = 480 twips
    spacing.set(_w("lineRule"), "exact")
    spacing.set(_w("after"), "0")
    para.append(_make_run(text))
    log.debug("apa_body_paragraph generado (%d chars)", len(text))
    return para


def apa_figure_label(number: int, title: str) -> list[etree._Element]:
    """
    Bloque APA 7ª para etiqueta de figura:
    Línea 1: 'Figura N' (negrita)
    Línea 2: título en cursiva
    Ambas sin sangría de primera línea.
    """
    # Línea "Figura N"
    p_num = etree.Element(_w("p"))
    ppr1 = etree.SubElement(p_num, _w("pPr"))
    ind1 = etree.SubElement(ppr1, _w("ind"))
    ind1.set(_w("firstLine"), "0")
    p_num.append(_make_run(f"Figura {number}", bold=True))

    # Línea de título en cursiva
    p_title = etree.Element(_w("p"))
    ppr2 = etree.SubElement(p_title, _w("pPr"))
    ind2 = etree.SubElement(ppr2, _w("ind"))
    ind2.set(_w("firstLine"), "0")
    p_title.append(_make_run(title, italic=True))

    log.debug("apa_figure_label Figura %d generado", number)
    return [p_num, p_title]


def apa_figure_note(note_text: str) -> etree._Element:
    """
    Nota de figura APA 7ª:
    'Nota.' en cursiva seguido del texto de la nota, sin sangría.
    """
    para = etree.Element(_w("p"))
    ppr = etree.SubElement(para, _w("pPr"))
    ind = etree.SubElement(ppr, _w("ind"))
    ind.set(_w("firstLine"), "0")
    para.append(_make_run("Nota. ", italic=True))
    para.append(_make_run(note_text))
    log.debug("apa_figure_note generado")
    return para


def apa_reference_entry(text: str) -> etree._Element:
    """
    Entrada de referencia APA 7ª:
    Sangría francesa (hanging indent) de 1.27 cm = 720 twips.
    """
    para = _make_para("Normal", indent_left=720, hanging=720)
    para.append(_make_run(text))
    log.debug("apa_reference_entry generado: %r", text[:60])
    return para


def apa_in_text_citation(author: str, year: int,
                          page: str | None = None) -> str:
    """
    Retorna el string de cita en texto APA 7ª.
    Ej: (García, 2022) o (García, 2022, p. 45)
    """
    base = f"({author}, {year}"
    if page:
        base += f", p. {page}"
    return base + ")"


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO DE PLANTILLAS
# ─────────────────────────────────────────────────────────────────────────────
TEMPLATE_CATALOG: dict[str, str] = {
    "heading1":       "Encabezado Nivel 1 — centrado, negrita",
    "heading2":       "Encabezado Nivel 2 — izquierda, negrita",
    "heading3":       "Encabezado Nivel 3 — izquierda, negrita cursiva",
    "body_paragraph": "Párrafo cuerpo — sangría 1.27cm, doble espacio",
    "figure_label":   "Etiqueta de figura — número negrita + título cursiva",
    "figure_note":    "Nota de figura — 'Nota.' cursiva + texto",
    "reference":      "Referencia — sangría francesa 1.27cm",
}
