"""
PDF Prescription Generator using ReportLab.
Generates clean, professional medical prescription documents.
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)


def generate_prescription_pdf(rx_data: dict, doctor_info: dict | None = None, status: str = "draft") -> bytes:
    """Generate a PDF for the given prescription data dictionary and return raw bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'ClinicTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1a1c23'),
    )
    
    subtitle_style = ParagraphStyle(
        'ClinicSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#5c627c'),
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#22242d'),
        spaceAfter=4,
    )
    
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#2d3142'),
    )
    
    meta_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#41465b'),
    )
    
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1a1c23'),
    )
    
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1a1c23'),
    )
    
    table_hdr = ParagraphStyle(
        'TableHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#ffffff'),
    )

    story = []

    # 1. CLINIC / DOCTOR HEADER
    doc_name = (doctor_info.get("name") if doctor_info else "") or "Attending Physician"
    doc_spec = (doctor_info.get("specialty") if doctor_info else "") or "General Medicine"
    clinic_name = (doctor_info.get("clinic_name") if doctor_info else "") or "Asclepius Health Clinic"
    doc_phone = (doctor_info.get("phone") if doctor_info else "")

    header_data = [
        [
            Paragraph(f"<b>{clinic_name}</b>", title_style),
            Paragraph(f"<b>{doc_name}</b><br/>{doc_spec}" + (f"<br/>Ph: {doc_phone}" if doc_phone else ""), ParagraphStyle('DocRight', parent=subtitle_style, alignment=2))
        ]
    ]
    header_table = Table(header_data, colWidths=[320, 220])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#313546'), spaceAfter=12))

    # 2. PATIENT INFORMATION BAR
    pat = rx_data.get("patient") or {}
    pat_name = pat.get("name") or "—"
    pat_age = f"{pat.get('age')} yrs" if pat.get('age') else "—"
    pat_sex = pat.get("sex") or "—"
    rx_date = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    status_label = status.upper()

    pat_info = [
        [
            Paragraph(f"<b>Patient Name:</b> {pat_name}", body_style),
            Paragraph(f"<b>Age / Sex:</b> {pat_age} / {pat_sex}", body_style),
            Paragraph(f"<b>Date:</b> {rx_date}", body_style),
        ],
        [
            Paragraph(f"<b>Status:</b> {status_label}", body_style),
            Paragraph(f"<b>Prescription ID:</b> {rx_data.get('prescription_id', '—')}", body_style),
            Paragraph("", body_style)
        ]
    ]
    pat_table = Table(pat_info, colWidths=[200, 170, 170])
    pat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f4f5f8')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#d6d8e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7ef')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(pat_table)
    story.append(Spacer(1, 14))

    # 3. CLINICAL SUMMARY (Complaints & Diagnosis)
    complaints = rx_data.get("complaints") or []
    diagnosis = rx_data.get("diagnosis") or []

    if complaints or diagnosis:
        comp_str = ", ".join([f"{c.get('name', '')}" for c in complaints if c.get('name')]) if complaints else "None recorded"
        diag_str = ", ".join(diagnosis) if diagnosis else "Clinical evaluation"

        summary_data = [
            [Paragraph("<b>Presenting Complaints:</b>", meta_label), Paragraph(comp_str, body_style)],
            [Paragraph("<b>Clinical Diagnosis:</b>", meta_label), Paragraph(f"<b>{diag_str}</b>", body_style)],
        ]
        summary_table = Table(summary_data, colWidths=[140, 400])
        summary_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 12))

    # 4. MEDICATIONS (Rx Table)
    story.append(Paragraph("<b>Rx — Medication Schedule</b>", section_heading))
    meds = rx_data.get("medications") or []
    if meds:
        med_rows = [
            [
                Paragraph("<b>#</b>", table_hdr),
                Paragraph("<b>Medication Name</b>", table_hdr),
                Paragraph("<b>Dosage</b>", table_hdr),
                Paragraph("<b>Frequency</b>", table_hdr),
                Paragraph("<b>Duration</b>", table_hdr),
                Paragraph("<b>Instructions</b>", table_hdr),
            ]
        ]
        for i, m in enumerate(meds, 1):
            med_rows.append([
                Paragraph(str(i), table_cell),
                Paragraph(f"<b>{m.get('name', '')}</b>", table_cell_bold),
                Paragraph(m.get('dose', '—') or '—', table_cell),
                Paragraph(m.get('frequency', '—') or '—', table_cell),
                Paragraph(m.get('duration', '—') or '—', table_cell),
                Paragraph(m.get('instructions', '—') or m.get('route', '—') or '—', table_cell),
            ])

        med_table = Table(med_rows, colWidths=[24, 170, 76, 80, 80, 110])
        med_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#282b36')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fc')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d6d8e1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(med_table)
    else:
        story.append(Paragraph("<i>No medications prescribed.</i>", body_style))

    story.append(Spacer(1, 14))

    # 5. INVESTIGATIONS & ADVICE
    investigations = rx_data.get("investigations") or []
    advice = rx_data.get("advice") or []
    follow_up = rx_data.get("follow_up") or ""
    notes = rx_data.get("doctor_notes") or ""

    other_info = []
    if investigations:
        inv_str = ", ".join(investigations)
        other_info.append([Paragraph("<b>Investigations Advised:</b>", meta_label), Paragraph(inv_str, body_style)])
    if advice:
        adv_str = "<br/>".join([f"• {a}" for a in advice])
        other_info.append([Paragraph("<b>General Advice:</b>", meta_label), Paragraph(adv_str, body_style)])
    if follow_up:
        other_info.append([Paragraph("<b>Follow-up Visit:</b>", meta_label), Paragraph(f"<b>{follow_up}</b>", body_style)])
    if notes:
        other_info.append([Paragraph("<b>Clinical Notes:</b>", meta_label), Paragraph(notes, body_style)])

    if other_info:
        other_table = Table(other_info, colWidths=[140, 400])
        other_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(other_table)
        story.append(Spacer(1, 14))

    # 6. DOCTOR SIGNATURE & FOOTER
    story.append(Spacer(1, 20))
    sig_block = [
        [
            Paragraph("<i>* Generated securely via Asclepius Clinical Voice-to-Rx Assistant</i>", ParagraphStyle('FooterNote', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#888c9e'))),
            Paragraph(f"<b>{doc_name}</b><br/><font size=8 color='#5c627c'>Authorized Signatory</font>", ParagraphStyle('SigRight', parent=styles['Normal'], alignment=2, fontSize=9.5, leading=13))
        ]
    ]
    sig_table = Table(sig_block, colWidths=[320, 220])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether([sig_table]))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
