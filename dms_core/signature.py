"""Generisanje "digitalno potpisanog" rješenja (mock).

Kreira PDF (ako je reportlab dostupan) ili HTML fallback fajl sa:
  - Identifikacijom predmeta
  - Sažetkom odluke
  - Blokom za potpis službenika (ime, vrijeme, hash)
  - "Kvalifikovani elektronski potpis (demo)" oznakom

NIJE pravi digitalni potpis — služi samo za demonstraciju procesa.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple


BASE_DIR = Path(__file__).resolve().parent.parent
DECISIONS_DIR = BASE_DIR / "documents" / "decisions"
DECISIONS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("dms_portal.signature")


def _content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _try_generate_pdf(
    output_path: Path,
    request_id: int,
    request_type: str,
    citizen_name: str,
    officer_name: str,
    decision_text: str,
    issued_at: str,
) -> bool:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        )
        from reportlab.lib import colors
    except ImportError:
        return False

    try:
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title", parent=styles["Title"], fontSize=14, alignment=1, spaceAfter=12,
        )
        body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=11, leading=15)
        small_style = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=9, textColor=colors.grey)

        doc = SimpleDocTemplate(
            str(output_path), pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
        )

        story = [
            Paragraph("MINISTARSTVO UNUTRAŠNJIH POSLOVA CRNE GORE", title_style),
            Paragraph("DIGITALNI DMS PORTAL — RJEŠENJE", title_style),
            Spacer(1, 0.6 * cm),
            Paragraph(f"<b>Broj predmeta:</b> #{request_id}", body_style),
            Paragraph(f"<b>Tip zahtjeva:</b> {request_type}", body_style),
            Paragraph(f"<b>Korisnik:</b> {citizen_name}", body_style),
            Paragraph(f"<b>Datum izdavanja:</b> {issued_at}", body_style),
            Spacer(1, 0.4 * cm),
            Paragraph("<b>Odluka:</b>", body_style),
            Paragraph(decision_text.replace("\n", "<br/>"), body_style),
            Spacer(1, 1 * cm),
        ]

        sig_table = Table(
            [
                ["Službenik:", officer_name],
                ["Datum potpisa:", issued_at],
                ["Tip potpisa:", "Kvalifikovani elektronski potpis (DEMO)"],
            ],
            colWidths=[4 * cm, 11 * cm],
        )
        sig_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ]
            )
        )
        story.append(sig_table)
        story.append(Spacer(1, 0.6 * cm))
        story.append(
            Paragraph(
                "Ovaj dokument je generisan elektronski u okviru diplomskog DMS prototipa. "
                "Integritet je obezbijeđen SHA-256 sažetkom u dnu strane.",
                small_style,
            )
        )

        doc.build(story)
        return True
    except Exception:
        logger.exception("PDF generisanje neuspjelo request_id=%s", request_id)
        return False


def _render_html_fallback(
    output_path: Path,
    request_id: int,
    request_type: str,
    citizen_name: str,
    officer_name: str,
    decision_text: str,
    issued_at: str,
) -> None:
    decision_html = decision_text.replace("\n", "<br/>")
    content = f"""<!DOCTYPE html>
<html lang="sr">
<head>
<meta charset="utf-8">
<title>Rješenje #{request_id}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; max-width: 720px; margin: 40px auto; color: #1d1d1d; }}
  .header {{ text-align: center; margin-bottom: 24px; }}
  .sig {{ border: 1px solid #ccc; padding: 14px; margin-top: 24px; background: #fafafa; }}
  .meta {{ color: #666; font-size: 0.9rem; }}
</style>
</head>
<body>
<div class="header">
  <h2>MINISTARSTVO UNUTRAŠNJIH POSLOVA CRNE GORE</h2>
  <h3>Digitalni DMS portal — Rješenje</h3>
</div>
<p><b>Broj predmeta:</b> #{request_id}</p>
<p><b>Tip zahtjeva:</b> {request_type}</p>
<p><b>Korisnik:</b> {citizen_name}</p>
<p><b>Datum izdavanja:</b> {issued_at}</p>
<h4>Odluka</h4>
<p>{decision_html}</p>
<div class="sig">
  <p><b>Službenik:</b> {officer_name}</p>
  <p><b>Datum potpisa:</b> {issued_at}</p>
  <p><b>Tip potpisa:</b> Kvalifikovani elektronski potpis (DEMO)</p>
</div>
<p class="meta">Ovaj dokument je generisan elektronski. Integritet je obezbijeđen SHA-256 sažetkom.</p>
</body>
</html>
"""
    output_path.write_text(content, encoding="utf-8")


def generate_signed_decision(
    request_id: int,
    request_type: str,
    citizen_name: str,
    officer_name: str,
    decision_text: str,
) -> Tuple[str, str]:
    """Generiše potpisano rješenje. Vraća (file_path, sha256_hash)."""
    issued_at = datetime.now().strftime("%d.%m.%Y %H:%M")

    pdf_path = DECISIONS_DIR / f"rjesenje_{request_id}.pdf"
    ok = _try_generate_pdf(
        pdf_path, request_id, request_type, citizen_name, officer_name, decision_text, issued_at
    )

    if ok and pdf_path.exists():
        content = pdf_path.read_bytes()
        return str(pdf_path), _content_hash(content)

    # Fallback: HTML
    html_path = DECISIONS_DIR / f"rjesenje_{request_id}.html"
    _render_html_fallback(
        html_path, request_id, request_type, citizen_name, officer_name, decision_text, issued_at
    )
    content = html_path.read_bytes()
    return str(html_path), _content_hash(content)
