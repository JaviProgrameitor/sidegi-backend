"""
utils.py — Utilidades transversales: namespaces ECMA-376, logging y tipos comunes.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# NAMESPACES COMPLETOS DE OFFICE OPEN XML (ECMA-376)
# ─────────────────────────────────────────────────────────────────────────────
NS: dict[str, str] = {
    "w":   "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "r":   "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a":   "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "mc":  "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "ct":  "http://schemas.openxmlformats.org/package/2006/content-types",
    "cp":  "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "v":   "urn:schemas-microsoft-com:vml",
    "wp":  "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}

# Prefijo inverso: URI → prefijo para debugging
NS_INV: dict[str, str] = {v: k for k, v in NS.items()}


def qn(prefix: str, local: str) -> str:
    """Retorna el nombre calificado Clark-notation: {uri}local"""
    return f"{{{NS[prefix]}}}{local}"


# ─────────────────────────────────────────────────────────────────────────────
# LOGGER QUIRÚRGICO
# ─────────────────────────────────────────────────────────────────────────────
LOG_FORMAT = (
    "%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s"
)


def get_logger(name: str = "aldradoc") -> logging.Logger:
    """Retorna un logger configurado con handler a stderr para no romper MCP."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# ─────────────────────────────────────────────────────────────────────────────
# TIPOS COMUNES
# ─────────────────────────────────────────────────────────────────────────────
JsonDict = dict[str, Any]


def tag_local(tag: str) -> str:
    """Extrae el nombre local de un tag Clark-notation: '{uri}local' → 'local'"""
    return tag.split("}")[-1] if "}" in tag else tag


def tag_prefix(tag: str) -> str:
    """Extrae el URI y lo convierte en prefijo legible usando NS_INV."""
    if "}" in tag:
        uri = tag.split("}")[0][1:]
        return NS_INV.get(uri, uri[:20])
    return ""


def readable_tag(tag: str) -> str:
    """Retorna 'w:p', 'w:r', etc. desde un tag Clark-notation."""
    prefix = tag_prefix(tag)
    local = tag_local(tag)
    return f"{prefix}:{local}" if prefix else local


def validate_docx(path: Path) -> None:
    """Lanza ValueError si el archivo no existe o no es un DOCX válido."""
    if not path.exists():
        raise ValueError(f"Archivo no encontrado: {path}")
    if path.suffix.lower() != ".docx":
        raise ValueError(f"No es un archivo .docx: {path}")
