"""
surgeon.py — Motor quirúrgico de manipulación XML.
Opera directamente sobre el document.xml del contenedor DOCX
usando lxml + XPath para precisión de nodo. Zero format loss.
"""

from __future__ import annotations

import copy
import io
import shutil
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

from .utils import NS, JsonDict, get_logger, qn, readable_tag, validate_docx

log = get_logger("aldradoc.surgeon")

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
WORD_DOCUMENT  = "word/document.xml"
WORD_RELS      = "word/_rels/document.xml.rels"
CONTENT_TYPES  = "[Content_Types].xml"
REQUIRED_PARTS = {WORD_DOCUMENT, CONTENT_TYPES}


# ─────────────────────────────────────────────────────────────────────────────
# CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class DocxSurgeon:
    """
    Abre un .docx en memoria, expone el árbol XML como lxml.Element
    y permite cirugías XPath sin reescribir partes intactas del ZIP.
    """

    def __init__(self, docx_path: str | Path) -> None:
        self.path = Path(docx_path)
        validate_docx(self.path)
        self._zip_bytes: bytes = self.path.read_bytes()
        self._tree: etree._Element | None = None
        self._rels_tree: etree._Element | None = None
        self._dirty: bool = False
        self.pending_writes: dict[str, bytes] = {}
        log.info("DocxSurgeon inicializado para: %s", self.path.name)

    # ── Propiedad lazy: árbol del document.xml ────────────────────────────────
    @property
    def tree(self) -> etree._Element:
        if self._tree is None:
            self._tree = self._load_xml(WORD_DOCUMENT)
            log.debug("document.xml parseado (%d nodos raíz)", len(self._tree))
        return self._tree

    @property
    def rels_tree(self) -> etree._Element:
        if self._rels_tree is None:
            self._rels_tree = self._load_xml(WORD_RELS)
        return self._rels_tree

    def _load_xml(self, member: str) -> etree._Element:
        with zipfile.ZipFile(io.BytesIO(self._zip_bytes)) as z:
            raw = z.read(member)
        parser = etree.XMLParser(remove_blank_text=False, recover=True)
        return etree.fromstring(raw, parser)

    def _serialize_xml(self, element: etree._Element) -> bytes:
        return etree.tostring(
            element,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )

    # ── Inspección del árbol ──────────────────────────────────────────────────

    def inspect_tree(self, max_paragraphs: int = 100) -> list[JsonDict]:
        """
        Devuelve el mapa estructural de párrafos y runs del document.xml.
        Incluye: índice, paraId, estilo, texto completo y runs individuales.
        """
        log.info("Inspeccionando árbol XML (max %d párrafos)…", max_paragraphs)
        body = self.tree.find(qn("w", "body"))
        if body is None:
            raise RuntimeError("document.xml no contiene <w:body>")

        paragraphs = body.findall(f".//{qn('w', 'p')}")[:max_paragraphs]
        result: list[JsonDict] = []

        for idx, para in enumerate(paragraphs):
            # estilo
            ppr = para.find(qn("w", "pPr"))
            style_id = None
            if ppr is not None:
                ps = ppr.find(qn("w", "pStyle"))
                if ps is not None:
                    style_id = ps.get(qn("w", "val"))

            # paraId (w14)
            para_id = para.get(f"{{{NS['w14']}}}paraId") or para.get(f"{{{NS['w']}}}rsidR")

            # runs
            runs_data: list[JsonDict] = []
            for r_idx, run in enumerate(para.findall(qn("w", "r"))):
                rpr = run.find(qn("w", "rPr"))
                fmt: dict[str, bool] = {}
                if rpr is not None:
                    fmt = {
                        "bold":      rpr.find(qn("w", "b"))    is not None,
                        "italic":    rpr.find(qn("w", "i"))    is not None,
                        "underline": rpr.find(qn("w", "u"))    is not None,
                        "strike":    rpr.find(qn("w", "strike")) is not None,
                    }
                t_el = run.find(qn("w", "t"))
                text = (t_el.text or "") if t_el is not None else ""
                runs_data.append({
                    "run_index": r_idx,
                    "text": text,
                    "format": fmt,
                    "xpath": f"(//w:body//w:p)[{idx + 1}]/w:r[{r_idx + 1}]",
                })

            full_text = "".join(rd["text"] for rd in runs_data)
            log.debug("  p[%d] style=%s text=%r", idx, style_id, full_text[:60])

            result.append({
                "para_index": idx,
                "para_id":    para_id,
                "style":      style_id,
                "text":       full_text,
                "runs":       runs_data,
                "xpath":      f"(//w:body//w:p)[{idx + 1}]",
            })

        log.info("Inspeccion completada: %d parrafos encontrados", len(result))
        return result

    def inspect_images(self) -> list[dict[str, Any]]:
        """Extrae todas las imágenes (a:blip o v:imagedata) del documento."""
        log.info("Inspeccionando imágenes en el documento...")
        result = []
        
        # Buscar a:blip
        for blip in self.tree.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
            embed = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
            if embed:
                result.append({"rId": embed, "type": "blip"})
                
        # Buscar v:imagedata (formatos viejos / VML)
        for imagedata in self.tree.findall(".//{urn:schemas-microsoft-com:vml}imagedata"):
            embed = imagedata.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            if embed:
                result.append({"rId": embed, "type": "vml"})
                
        # Cruzar con rels para obtener el Target físico
        for item in result:
            rel_node = self.rels_tree.find(f".//{{http://schemas.openxmlformats.org/package/2006/relationships}}Relationship[@Id='{item['rId']}']")
            if rel_node is not None:
                item["target"] = rel_node.get("Target")
                
        # Deduplicar
        unique_results = list({f"{r['rId']}": r for r in result}.values())
        log.info("Imágenes encontradas: %s", unique_results)
        return unique_results

    # ── Reemplazo quirúrgico de texto ─────────────────────────────────────────

    def surgical_replace(
        self,
        target_text: str,
        replacement_text: str,
        occurrence: int = 1,
    ) -> dict[str, Any]:
        """
        Localiza 'target_text' dentro de runs <w:t> y lo reemplaza
        preservando 100% del formato del <w:r> que lo contiene.

        Maneja runs simples Y runs fragmentados (texto dividido entre
        varios <w:r> consecutivos por autocorrección de Word).

        occurrence: qué aparición reemplazar (1 = primera, -1 = todas).
        """
        log.info("surgical_replace: %r → %r (occurrence=%d)",
                 target_text, replacement_text, occurrence)

        body = self.tree.find(qn("w", "body"))
        if body is None:
            raise RuntimeError("No se encontró <w:body>")

        count_replaced = 0
        count_found = 0

        for para in body.iter(qn("w", "p")):
            # Recolectar todos los runs del párrafo con su texto
            runs = para.findall(f".//{qn('w', 'r')}")
            if not runs:
                continue

            # Construir texto concatenado del párrafo
            para_text = "".join(
                (r.find(qn("w", "t")).text or "")
                for r in runs
                if r.find(qn("w", "t")) is not None
            )

            if target_text not in para_text:
                continue

            count_found += 1

            # ─ Estrategia: encontrar el run que contiene el inicio del target ─
            # Intento 1: target en un solo run
            replaced = False
            for run in runs:
                t_el = run.find(qn("w", "t"))
                if t_el is None:
                    continue
                run_text = t_el.text or ""
                if target_text in run_text:
                    old = run_text
                    t_el.text = run_text.replace(target_text, replacement_text, 1)
                    # Preservar xml:space si el texto tiene espacios al borde
                    if (t_el.text or "").strip() != (t_el.text or ""):
                        t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                    log.info("  [SINGLE-RUN] '%s' → '%s' en run", old, t_el.text)
                    replaced = True
                    count_replaced += 1
                    self._dirty = True
                    break

            # Intento 2: target fragmentado entre runs consecutivos
            if not replaced:
                log.debug("  Intentando reemplazo multi-run para %r", target_text)
                replaced = self._replace_fragmented(runs, target_text, replacement_text)
                if replaced:
                    count_replaced += 1
                    self._dirty = True

            if occurrence != -1 and count_replaced >= occurrence:
                break

        result = {
            "target":      target_text,
            "replacement": replacement_text,
            "occurrences_found":    count_found,
            "occurrences_replaced": count_replaced,
            "dirty": self._dirty,
        }
        log.info("surgical_replace completado: %s", result)
        return result

    def _replace_fragmented(
        self,
        runs: list[etree._Element],
        target: str,
        replacement: str,
    ) -> bool:
        """
        Intenta reemplazar texto que está fragmentado en múltiples <w:r> consecutivos.
        Junta el texto de todos los runs, localiza el target, y reconstruye
        el primer run con el texto completo, vaciando los demás.
        """
        texts = []
        t_elements: list[tuple[etree._Element, etree._Element]] = []

        for run in runs:
            t_el = run.find(qn("w", "t"))
            if t_el is not None:
                texts.append(t_el.text or "")
                t_elements.append((run, t_el))

        joined = "".join(texts)
        if target not in joined:
            return False

        new_joined = joined.replace(target, replacement, 1)

        # Poner todo el texto en el primer run y vaciar el resto
        if t_elements:
            first_run, first_t = t_elements[0]
            first_t.text = new_joined
            if new_joined.strip() != new_joined:
                first_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            for _, t_el in t_elements[1:]:
                t_el.text = ""
            log.info("  [MULTI-RUN] fragmentado resuelto, %d runs fusionados",
                     len(t_elements))
            return True
        return False

    # ── Inyección de estructura APA ───────────────────────────────────────────

    def inject_apa_structure(
        self,
        anchor_text: str,
        nodes: list[etree._Element],
        position: str = "after",
    ) -> dict[str, Any]:
        """
        Inyecta una lista de nodos XML (plantillas APA) antes o después del
        párrafo que contiene 'anchor_text'. Usa XPath para localización exacta.

        position: 'before' | 'after' | 'replace'
        """
        log.info("inject_apa_structure: anchor=%r, %d nodos, position=%s",
                 anchor_text, len(nodes), position)

        body = self.tree.find(qn("w", "body"))
        if body is None:
            raise RuntimeError("No se encontró <w:body>")

        anchor_para: etree._Element | None = None
        anchor_idx: int = -1

        for idx, child in enumerate(body):
            if child.tag != qn("w", "p"):
                continue
            para_text = "".join(
                (t.text or "")
                for t in child.iter(qn("w", "t"))
            )
            if anchor_text in para_text:
                anchor_para = child
                anchor_idx = idx
                log.debug("Anclaje encontrado en body[%d]: %r", idx, para_text[:80])
                break

        if anchor_para is None:
            msg = f"No se encontró ningún párrafo con el texto: {anchor_text!r}"
            log.error(msg)
            return {"success": False, "error": msg}

        # Inyectar nodos en el orden correcto
        if position == "after":
            for offset, node in enumerate(nodes):
                body.insert(anchor_idx + 1 + offset, copy.deepcopy(node))
        elif position == "before":
            for offset, node in enumerate(nodes):
                body.insert(anchor_idx + offset, copy.deepcopy(node))
        elif position == "replace":
            body.remove(anchor_para)
            for offset, node in enumerate(nodes):
                body.insert(anchor_idx + offset, copy.deepcopy(node))
        else:
            raise ValueError(f"position inválido: {position!r}. Usa 'before', 'after' o 'replace'")

        self._dirty = True
        result = {
            "success":    True,
            "anchor":     anchor_text,
            "position":   position,
            "nodes_injected": len(nodes),
            "anchor_body_index": anchor_idx,
        }
        log.info("Inyeccion completada: %s", result)
        return result

    # ── Inyección y Reemplazo de Imágenes ─────────────────────────────────────

    def surgical_replace_image(self, r_id: str | None, new_image_path: str | Path, zip_target: str | None = None) -> dict[str, Any]:
        """Sustituye físicamente una imagen en el ZIP. Puede buscar por r_id en document.xml.rels o usar zip_target directo."""
        log.info("surgical_replace_image: r_id=%r, zip_target=%r, path=%r", r_id, zip_target, new_image_path)
        
        if not zip_target:
            if not r_id:
                return {"success": False, "error": "Se debe proveer r_id o zip_target"}
            rel_node = self.rels_tree.find(f".//{{http://schemas.openxmlformats.org/package/2006/relationships}}Relationship[@Id='{r_id}']")
            if rel_node is None:
                return {"success": False, "error": f"No se encontró la relación {r_id} en document.xml.rels"}
            
            target = rel_node.get("Target")
            if not target:
                return {"success": False, "error": f"La relación {r_id} no tiene atributo Target"}
                
            zip_target = target[1:] if target.startswith("/") else f"word/{target}"
            
        img_path = Path(new_image_path)
        if not img_path.exists():
            return {"success": False, "error": f"La nueva imagen no existe: {img_path}"}
            
        img_bytes = img_path.read_bytes()
        self.pending_writes[zip_target] = img_bytes
        self._dirty = True
        
        result = {"success": True, "r_id": r_id, "replaced_file": zip_target, "bytes_written": len(img_bytes)}
        log.info("Reemplazo de imagen preparado: %s", result)
        return result

    def surgical_inject_image(self, xpath_expr: str, new_image_path: str | Path) -> dict[str, Any]:
        """Inyecta un nuevo nodo <w:drawing> y crea sus relaciones en el DOCX."""
        # Encontrar ID máximo
        rels = self.rels_tree.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        max_id = 0
        for rel in rels:
            rid = rel.get("Id")
            if rid and rid.startswith("rId"):
                try:
                    num = int(rid[3:])
                    if num > max_id: max_id = num
                except ValueError: pass
        
        new_rid = f"rId{max_id + 1}"
        img_path = Path(new_image_path)
        if not img_path.exists():
            return {"success": False, "error": f"La imagen no existe: {img_path}"}
            
        img_bytes = img_path.read_bytes()
        ext = img_path.suffix.lower() or ".png"
        target_name = f"media/image_injected_{max_id + 1}{ext}"
        zip_target = f"word/{target_name}"
        
        # Registrar en rels
        new_rel = etree.SubElement(self.rels_tree, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        new_rel.set("Id", new_rid)
        new_rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
        new_rel.set("Target", target_name)
        
        self.pending_writes[zip_target] = img_bytes
        
        # Inyectar <w:drawing>
        nodes = self.find_by_xpath(xpath_expr)
        if not nodes:
            return {"success": False, "error": f"XPath no encontró ningún nodo: {xpath_expr}"}
            
        cx = 3 * 914400  # 3 pulgadas aprox
        cy = 3 * 914400
        
        drawing_xml = f"""
        <w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
            <wp:inline distT="0" distB="0" distL="0" distR="0">
                <wp:extent cx="{cx}" cy="{cy}"/>
                <wp:effectExtent l="0" t="0" r="0" b="0"/>
                <wp:docPr id="{max_id + 1}" name="InjectedImage{max_id + 1}"/>
                <wp:cNvGraphicFramePr>
                    <a:graphicFrameLocks noChangeAspect="1"/>
                </wp:cNvGraphicFramePr>
                <a:graphic>
                    <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                        <pic:pic>
                            <pic:nvPicPr>
                                <pic:cNvPr id="{max_id + 1}" name="InjectedImage{ext}"/>
                                <pic:cNvPicPr/>
                            </pic:nvPicPr>
                            <pic:blipFill>
                                <a:blip r:embed="{new_rid}"/>
                                <a:stretch>
                                    <a:fillRect/>
                                </a:stretch>
                            </pic:blipFill>
                            <pic:spPr>
                                <a:xfrm>
                                    <a:off x="0" y="0"/>
                                    <a:ext cx="{cx}" cy="{cy}"/>
                                </a:xfrm>
                                <a:prstGeom prst="rect">
                                    <a:avLst/>
                                </a:prstGeom>
                            </pic:spPr>
                        </pic:pic>
                    </a:graphicData>
                </a:graphic>
            </wp:inline>
        </w:drawing>
        """
        drawing_el = etree.fromstring(drawing_xml.strip())
        
        for node in nodes:
            r_el = etree.SubElement(node, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r")
            r_el.append(copy.deepcopy(drawing_el))
            
        self._dirty = True
        return {"success": True, "injected_rId": new_rid, "target": zip_target, "xpath": xpath_expr}

    # ── Mutación Quirúrgica de Estilos (Full Format Control) ──────────────────

    def surgical_style_edit(
        self,
        xpath_expr: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Inyecta o modifica propiedades OOXML en un nodo específico (w:p o w:r).
        
        properties: {
            "align": "left|center|right|both",
            "size": int (medios puntos, ej. 24 = 12pt),
            "font": str (ej. "Arial"),
            "bold": bool,
            "italic": bool,
            "indent_left": int (twips),
            "indent_hanging": int (twips)
        }
        """
        log.info("surgical_style_edit en %r con propiedades: %r", xpath_expr, properties)
        nodes = self.find_by_xpath(xpath_expr)
        if not nodes:
            return {"success": False, "error": f"XPath no encontró ningún nodo: {xpath_expr}"}

        modified_count = 0
        for node in nodes:
            if node.tag == qn("w", "p"):
                self._apply_pPr(node, properties)
                # Aplicar también a todos los runs hijos para que el texto cambie
                for run in node.findall(f".//{qn('w', 'r')}"):
                    self._apply_rPr(run, properties)
                modified_count += 1
            elif node.tag == qn("w", "r"):
                self._apply_rPr(node, properties)
                modified_count += 1
            else:
                log.warning("El nodo objetivo no es w:p ni w:r: %s", node.tag)

        self._dirty = modified_count > 0
        return {
            "success": True,
            "nodes_modified": modified_count,
            "xpath": xpath_expr,
            "dirty": self._dirty
        }

    def _apply_pPr(self, p_node: etree._Element, props: dict[str, Any]) -> None:
        pPr = p_node.find(qn("w", "pPr"))
        if pPr is None:
            pPr = etree.Element(qn("w", "pPr"))
            p_node.insert(0, pPr)

        if "align" in props:
            jc = pPr.find(qn("w", "jc"))
            if jc is None:
                jc = etree.SubElement(pPr, qn("w", "jc"))
            jc.set(qn("w", "val"), props["align"])

        if "indent_left" in props or "indent_hanging" in props:
            ind = pPr.find(qn("w", "ind"))
            if ind is None:
                ind = etree.SubElement(pPr, qn("w", "ind"))
            if "indent_left" in props:
                ind.set(qn("w", "left"), str(props["indent_left"]))
            if "indent_hanging" in props:
                ind.set(qn("w", "hanging"), str(props["indent_hanging"]))

        # Apply run properties to the paragraph mark if present
        self._apply_rPr(pPr, props)

    def _apply_rPr(self, parent_node: etree._Element, props: dict[str, Any]) -> None:
        rPr = parent_node.find(qn("w", "rPr"))
        if rPr is None:
            if any(k in props for k in ["size", "font", "bold", "italic"]):
                rPr = etree.Element(qn("w", "rPr"))
                parent_node.insert(0, rPr)
            else:
                return

        if "size" in props:
            sz = rPr.find(qn("w", "sz"))
            if sz is None:
                sz = etree.SubElement(rPr, qn("w", "sz"))
            sz.set(qn("w", "val"), str(props["size"]))
            szCs = rPr.find(qn("w", "szCs"))
            if szCs is None:
                szCs = etree.SubElement(rPr, qn("w", "szCs"))
            szCs.set(qn("w", "val"), str(props["size"]))

        if "font" in props:
            rFonts = rPr.find(qn("w", "rFonts"))
            if rFonts is None:
                rFonts = etree.SubElement(rPr, qn("w", "rFonts"))
            rFonts.set(qn("w", "ascii"), props["font"])
            rFonts.set(qn("w", "hAnsi"), props["font"])
            rFonts.set(qn("w", "cs"), props["font"])

        if props.get("bold") is True:
            if rPr.find(qn("w", "b")) is None:
                etree.SubElement(rPr, qn("w", "b"))
        elif props.get("bold") is False:
            b_el = rPr.find(qn("w", "b"))
            if b_el is not None:
                rPr.remove(b_el)

        if props.get("italic") is True:
            if rPr.find(qn("w", "i")) is None:
                etree.SubElement(rPr, qn("w", "i"))
        elif props.get("italic") is False:
            i_el = rPr.find(qn("w", "i"))
            if i_el is not None:
                rPr.remove(i_el)

    # ── Commit: reempaquetado seguro del ZIP ──────────────────────────────────


    def commit_changes(self, output_path: str | Path | None = None) -> dict[str, Any]:
        """
        Reempaqueta el DOCX con el document.xml modificado.
        Preserva: [Content_Types].xml, relaciones, imágenes y todos
        los demás miembros del ZIP sin tocarlos.

        Si output_path es None, sobreescribe el archivo original.
        """
        if not self._dirty:
            log.warning("commit_changes llamado sin cambios pendientes. Abortando.")
            return {"committed": False, "reason": "no hay cambios pendientes"}

        out = Path(output_path) if output_path else self.path
        log.info("Committing cambios a: %s", out)

        # Serializar el árbol modificado
        new_doc_xml = self._serialize_xml(self.tree)
        log.debug("document.xml serializado (%d bytes)", len(new_doc_xml))

        # Construir el nuevo ZIP en memoria
        out_buffer = io.BytesIO()
        
        self.pending_writes[WORD_DOCUMENT] = new_doc_xml
        if self._rels_tree is not None:
            self.pending_writes[WORD_RELS] = self._serialize_xml(self.rels_tree)

        with zipfile.ZipFile(io.BytesIO(self._zip_bytes)) as src_zip:
            names = set(src_zip.namelist())
            missing = REQUIRED_PARTS - names
            if missing:
                raise RuntimeError(f"DOCX corrupto: faltan partes: {missing}")

            with zipfile.ZipFile(out_buffer, "w", zipfile.ZIP_DEFLATED) as dst_zip:
                for item in src_zip.infolist():
                    if item.filename in self.pending_writes:
                        dst_zip.writestr(item, self.pending_writes.pop(item.filename))
                        log.debug("  [REPLACED] %s", item.filename)
                    else:
                        dst_zip.writestr(item, src_zip.read(item.filename))
                        
                # Escribir archivos nuevos que no existían en el ZIP
                for filename, data in self.pending_writes.items():
                    dst_zip.writestr(filename, data)
                    log.debug("  [ADDED] %s", filename)

        # Escribir a disco
        out.write_bytes(out_buffer.getvalue())
        size_kb = out.stat().st_size / 1024
        self._dirty = False

        result = {
            "committed":   True,
            "output_path": str(out),
            "size_kb":     round(size_kb, 1),
            "xml_size_bytes": len(new_doc_xml),
        }
        log.info("Commit exitoso: %s (%.1f KB)", out.name, size_kb)
        return result

    # ── Utilidades adicionales ────────────────────────────────────────────────

    def find_by_xpath(self, xpath_expr: str) -> list[etree._Element]:
        """Ejecuta una expresión XPath arbitraria sobre el document.xml."""
        log.debug("XPath: %s", xpath_expr)
        return self.tree.xpath(xpath_expr, namespaces=NS)

    def get_styles_list(self) -> list[str]:
        """Lista todos los estilos usados en el documento."""
        styles: list[str] = []
        for ps in self.tree.iter(qn("w", "pStyle")):
            val = ps.get(qn("w", "val"))
            if val and val not in styles:
                styles.append(val)
        for rs in self.tree.iter(qn("w", "rStyle")):
            val = rs.get(qn("w", "val"))
            if val and val not in styles:
                styles.append(val)
        log.debug("Estilos encontrados: %s", styles)
        return sorted(styles)

    def discard_changes(self) -> None:
        """Descarta todos los cambios en memoria y recarga desde disco."""
        self._tree = None
        self._rels_tree = None
        self._dirty = False
        log.info("Cambios descartados. Árbol recargado.")
