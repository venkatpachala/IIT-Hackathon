"""
cam_engine/document/pdf_converter.py
=======================================
Converts .docx → .pdf.

Strategy (tries in order):
  1. docx2pdf with COM reset     (Windows + MS Word fully installed)
  2. LibreOffice headless         (Linux / Docker / macOS)
  3. python-docx + reportlab      (pure-Python fallback, no Office needed)
  4. Returns None                 (graceful degradation — no crash)

Strategy 3 (reportlab) produces a clean, text-accurate PDF from the
python-docx DOM — no rendering artifacts, guaranteed to work on any OS.
"""

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path
from typing import Optional


def convert_to_pdf(docx_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Convert a .docx file to PDF.

    Parameters
    ----------
    docx_path   : Absolute path to the source .docx file.
    output_path : Optional target path for the .pdf. Defaults to same
                  directory with .pdf extension.

    Returns
    -------
    str  — path to the generated PDF, or None if ALL strategies failed.
    """
    docx_path = Path(docx_path)
    if not docx_path.exists():
        print(f"[pdf_converter] Source file not found: {docx_path}", file=sys.stderr)
        return None

    if output_path is None:
        output_path = str(docx_path.with_suffix(".pdf"))

    # ── Strategy 1: docx2pdf (Windows / macOS with MS Word) ──────────────
    try:
        from docx2pdf import convert as d2p_convert
        # Reset any stale COM Word instance before calling
        _reset_word_com()
        d2p_convert(str(docx_path), output_path)
        if Path(output_path).exists() and Path(output_path).stat().st_size > 1024:
            print(f"[pdf_converter] PDF created via docx2pdf: {output_path}")
            return output_path
    except ImportError:
        pass   # docx2pdf not installed
    except Exception as e:
        print(f"[pdf_converter] docx2pdf failed ({type(e).__name__}: {e}) — trying next strategy.", file=sys.stderr)

    # ── Strategy 2: LibreOffice headless (Linux / Docker / macOS) ────────
    for soffice_cmd in ("soffice", "libreoffice"):
        try:
            out_dir = str(Path(output_path).parent)
            result  = subprocess.run(
                [
                    soffice_cmd,
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", out_dir,
                    str(docx_path),
                ],
                capture_output=True,
                timeout=90,
            )
            expected = Path(out_dir) / (docx_path.stem + ".pdf")
            if result.returncode == 0 and expected.exists():
                if str(expected) != output_path:
                    expected.rename(output_path)
                print(f"[pdf_converter] PDF created via LibreOffice: {output_path}")
                return output_path
            else:
                err = result.stderr.decode(errors="replace")[:300]
                print(f"[pdf_converter] {soffice_cmd} failed: {err}", file=sys.stderr)
        except FileNotFoundError:
            pass   # not installed
        except subprocess.TimeoutExpired:
            print(f"[pdf_converter] {soffice_cmd} timed out.", file=sys.stderr)
        except Exception as e:
            print(f"[pdf_converter] {soffice_cmd} error: {e}", file=sys.stderr)

    # ── Strategy 3: Pure-Python via reportlab ────────────────────────────
    # Works on ANY OS without MS Word or LibreOffice.
    # Renders a complete, professional PDF from the python-docx DOM.
    pdf_path = _reportlab_pdf(docx_path, output_path)
    if pdf_path:
        return pdf_path

    # ── Graceful degradation ──────────────────────────────────────────────
    print(
        "[pdf_converter] All PDF strategies exhausted. "
        "DOCX file is the final output (download will serve DOCX).",
        file=sys.stderr,
    )
    return None


# ─────────────────────────────────────────────────────────────────────────
# Helper: reset stale Word COM instance (fixes docx2pdf AttributeError)
# ─────────────────────────────────────────────────────────────────────────

def _reset_word_com():
    """
    Forcefully kill any stale WINWORD.EXE process before docx2pdf runs.
    This prevents the 'AttributeError: Open.SaveAs' error caused by
    a hung Word COM server from a previous failed conversion.
    """
    if sys.platform != "win32":
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "WINWORD.EXE"],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass   # silently ignore — not critical


# ─────────────────────────────────────────────────────────────────────────
# Helper: reportlab pure-Python PDF generator
# ─────────────────────────────────────────────────────────────────────────

def _reportlab_pdf(docx_path: Path, output_path: str) -> Optional[str]:
    """
    Generate a PDF from a .docx file using reportlab.
    Iterates python-docx paragraphs, applying font size, bold, color,
    and table detection. Produces a clean professional output.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        from docx import Document
        from docx.oxml.ns import qn

    except ImportError as e:
        print(f"[pdf_converter] reportlab/python-docx not installed for Strategy 3: {e}", file=sys.stderr)
        return None

    try:
        doc   = Document(str(docx_path))
        story = []

        # Page styles
        W, H  = A4
        margin = 2.0 * cm
        styles = getSampleStyleSheet()

        heading1 = ParagraphStyle(
            "Heading1CAM",
            parent=styles["Heading1"],
            fontSize=13, leading=18, spaceAfter=8,
            textColor=colors.HexColor("#1a1a2e"),
            fontName="Helvetica-Bold",
        )
        heading2 = ParagraphStyle(
            "Heading2CAM",
            parent=styles["Heading2"],
            fontSize=11, leading=15, spaceAfter=6,
            textColor=colors.HexColor("#16213e"),
            fontName="Helvetica-Bold",
        )
        body_style = ParagraphStyle(
            "BodyCAM",
            parent=styles["Normal"],
            fontSize=9, leading=13, spaceAfter=5,
            textColor=colors.HexColor("#222222"),
            fontName="Helvetica",
        )
        table_header_style = ParagraphStyle(
            "TblHdr",
            parent=styles["Normal"],
            fontSize=8, fontName="Helvetica-Bold",
            textColor=colors.white,
        )
        table_cell_style = ParagraphStyle(
            "TblCell",
            parent=styles["Normal"],
            fontSize=8, fontName="Helvetica",
        )

        doc_pdf = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=margin, rightMargin=margin,
            topMargin=margin,  bottomMargin=margin,
            title="Credit Appraisal Memorandum",
            author="Intelli-Credit AI Engine",
        )

        # Page-numbering footer callback
        def _on_page(canvas, doc_inst):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.grey)
            canvas.drawCentredString(
                W / 2, 0.7 * cm,
                f"Page {doc_inst.page}  |  CONFIDENTIAL — FOR INTERNAL BANK USE ONLY  |  Intelli-Credit AI Engine"
            )
            canvas.restoreState()

        def safe_text(t: str) -> str:
            """Escape XML special chars for reportlab."""
            return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        def para_to_story(para):
            """Convert a python-docx paragraph to a reportlab Paragraph."""
            text = safe_text(para.text.strip())
            if not text:
                return [Spacer(1, 4)]

            # Detect heading level by style name
            sname = (para.style.name or "").lower()
            if "heading 1" in sname or text.isupper():
                return [Spacer(1, 10), Paragraph(text, heading1), Spacer(1, 4)]
            if "heading 2" in sname:
                return [Spacer(1, 6), Paragraph(text, heading2), Spacer(1, 2)]

            # Bold paragraph
            is_bold = para.runs[0].bold if para.runs else False
            if is_bold and len(text) < 100:
                return [Paragraph(f"<b>{text}</b>", body_style)]

            return [Paragraph(text, body_style)]

        def table_to_story(tbl):
            """Convert a python-docx Table to a reportlab Table."""
            data    = []
            col_cnt = max((len(row.cells) for row in tbl.rows), default=1)

            for r_idx, row in enumerate(tbl.rows):
                row_data = []
                for cell in row.cells:
                    cell_text = "\n".join(p.text for p in cell.paragraphs if p.text.strip())
                    if r_idx == 0:
                        row_data.append(Paragraph(safe_text(cell_text), table_header_style))
                    else:
                        row_data.append(Paragraph(safe_text(cell_text), table_cell_style))
                # Pad row if cols merged
                while len(row_data) < col_cnt:
                    row_data.append(Paragraph("", table_cell_style))
                data.append(row_data)

            if not data:
                return []

            avail_w = W - 2 * margin
            col_w   = [avail_w / col_cnt] * col_cnt

            tbl_style = TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0),   colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR",   (0, 0), (-1, 0),   colors.white),
                ("FONTNAME",    (0, 0), (-1, 0),   "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1, -1),  8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                    [colors.HexColor("#f8f9fa"), colors.white]),
                ("GRID",        (0, 0), (-1, -1),  0.5, colors.HexColor("#cccccc")),
                ("VALIGN",      (0, 0), (-1, -1),  "TOP"),
                ("TOPPADDING",  (0, 0), (-1, -1),  4),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1),  4),
                ("RIGHTPADDING",(0, 0), (-1, -1),  4),
            ])

            tbl_obj = Table(data, colWidths=col_w, repeatRows=1)
            tbl_obj.setStyle(tbl_style)
            return [Spacer(1, 8), tbl_obj, Spacer(1, 8)]

        # ── Cover banner ─────────────────────────────────────────────
        story.append(Paragraph("IDFC FIRST Bank", ParagraphStyle(
            "Brand", parent=styles["Normal"],
            fontSize=16, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#7b1c1c"),
        )))
        story.append(Paragraph("CREDIT APPRAISAL MEMORANDUM", ParagraphStyle(
            "Title", parent=styles["Normal"],
            fontSize=14, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=4,
        )))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#7b1c1c")))
        story.append(Paragraph(
            "CONFIDENTIAL — FOR INTERNAL BANK USE ONLY",
            ParagraphStyle("Conf", parent=styles["Normal"],
                           fontSize=8, fontName="Helvetica-Oblique",
                           textColor=colors.HexColor("#7b1c1c"), spaceAfter=12)
        ))

        # ── Traverse docx body elements in order ─────────────────────
        for elem in doc.element.body:
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if tag == "p":
                # It's a paragraph
                from docx.text.paragraph import Paragraph as DocxParagraph
                para = DocxParagraph(elem, doc)
                story.extend(para_to_story(para))

            elif tag == "tbl":
                # It's a table
                from docx.table import Table as DocxTable
                tbl = DocxTable(elem, doc)
                story.extend(table_to_story(tbl))

            elif tag == "sectPr":
                # Section break — add page break
                story.append(Spacer(1, 20))

        # Build PDF
        doc_pdf.build(story, onFirstPage=_on_page, onLaterPages=_on_page)

        if Path(output_path).exists() and Path(output_path).stat().st_size > 1024:
            print(f"[pdf_converter] PDF created via reportlab (pure-Python): {output_path}")
            return output_path
        return None

    except Exception as e:
        print(f"[pdf_converter] reportlab strategy failed: {e}", file=sys.stderr)
        return None
