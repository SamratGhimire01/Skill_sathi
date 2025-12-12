# backend/utils/pdf_generator.py (FINAL - USING YOUR EXPORTED POSITIONS)

from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, lightgrey
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import qrcode
from PIL import Image, ImageOps, ImageDraw
from datetime import datetime
import os

# Colors
COLOR_DARK_TEXT = HexColor("#2B3640")
COLOR_GREEN_SCRIPT = HexColor("#008000")
COLOR_SUBTLE_TEXT = HexColor("#272A30")
COLOR_STATUS_VALID = HexColor("#059669")
COLOR_STATUS_REVOKED = HexColor("#EF4444")

def make_circular_image(image_bytes, size=(150, 150)):
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGBA")
        img = ImageOps.fit(img, size, centering=(0.5, 0.5))
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=255)
        output = ImageOps.fit(img, size, centering=(0.5, 0.5))
        output.putalpha(mask)
        buf = BytesIO()
        output.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None

def generate_certificate_pdf(certificate_data: dict, is_preview: bool = False, company_branding: dict = None):
    buffer = BytesIO()
    page_width, page_height = landscape(A4)  # 842 x 595 points
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    # Coordinate conversion helper
    def html_to_pdf_y(html_top):
        return page_height - html_top

    # Paths
    assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    bg_image_path = os.path.join(assets_dir, "certificate_bg_new.png")
    font_path = os.path.join(assets_dir, "GreatVibes-Regular.ttf")

    # 1. BACKGROUND
    if os.path.exists(bg_image_path):
        c.drawImage(bg_image_path, 0, 0, width=page_width, height=page_height)
    else:
        c.setFillColor(white)
        c.rect(0, 0, page_width, page_height, fill=True)

    # 2. FONTS
    script_font = "Helvetica-Bold"
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('GreatVibes', font_path))
            script_font = 'GreatVibes'
        except Exception:
            pass

        # --- 3. DYNAMIC DATA (FINAL ADJUSTMENT: LOWER RIGHT SIDE + FIX QR) ---

    # Recipient Name — LOWERED by 40 points
    c.setFont(script_font, 60)
    c.setFillColor(COLOR_GREEN_SCRIPT)
    recipient_name = certificate_data['recipient_name'].title()
    c.drawString(63, html_to_pdf_y(269) - 40, recipient_name)

    # Course Title — LOWERED by 40 points
    c.setFont("Helvetica-Bold", 40)
    c.setFillColor(COLOR_GREEN_SCRIPT)
    course_title = certificate_data['course_title'].upper()
    c.drawString(63, html_to_pdf_y(374) - 40, course_title)

    # Issue Date — LOWERED by 20 points
    c.setFont("Helvetica", 14)
    c.setFillColor(COLOR_SUBTLE_TEXT)
    issue_date_str = datetime.now().strftime("%d %b %Y")
    if certificate_data.get('completion_date'):
        try:
            issue_date_str = certificate_data['completion_date'].strftime("%d %b %Y")
        except:
            issue_date_str = str(certificate_data['completion_date'])
    c.drawString(453, html_to_pdf_y(294) - 20, issue_date_str)

    # Course Duration — LOWERED by 20 points
    duration_text = certificate_data.get('course_duration', "Duration Not Set")
    c.drawString(452, html_to_pdf_y(348) - 20, duration_text)

    # SHA-256 Digital Signature — LOWERED by 20 points
    sha_hash = certificate_data.get('sha_hash', 'INVALID HASH')
    if is_preview or sha_hash == 'INVALID HASH' or len(sha_hash) < 60:
        sha_hash_display = "0000-0000-0000 (PENDING)" if is_preview else "INVALID HASH"
    else:
        sha_hash_display = sha_hash
    

    
    styles = getSampleStyleSheet()
    
    style = styles['Normal']
    style.fontName = 'Helvetica'
    style.fontSize = 10
    style.textColor = COLOR_SUBTLE_TEXT
    style.leading = 12
    p = Paragraph(sha_hash_display, style)
    p.wrapOn(c, 200, 50)
    p.drawOn(c, 452, html_to_pdf_y(403 + 10) - 15)

    # Certificate ID — LOWERED by 20 points
    cert_id = certificate_data['certificate_uid']
    c.drawString(692, html_to_pdf_y(294) - 20, cert_id)

    # Status — LOWERED by 20 points
    status_text = "VALID"
    status_color = COLOR_STATUS_VALID
    if is_preview:
        status_text = "PENDING"
        status_color = COLOR_SUBTLE_TEXT
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(status_color)
    c.drawString(689, html_to_pdf_y(347) - 20, status_text)

        # --- 4. RECIPIENT PHOTO — LOWERED by 15 points ---
    if certificate_data.get("recipient_photo"):
        photo_stream = make_circular_image(certificate_data["recipient_photo"], size=(120, 120))
        if photo_stream:
            c.drawImage(ImageReader(photo_stream), 644+10, html_to_pdf_y(76 + 90) - 39, width=120, height=120, mask='auto')

    # --- 5. SIGNATURE ---
    if company_branding and company_branding.get('signature_bytes'):
        try:
            sig_img = ImageReader(BytesIO(company_branding['signature_bytes']))
            c.drawImage(sig_img, 62, html_to_pdf_y(482 + 35), width=120, height=35, mask='auto', preserveAspectRatio=True)
        except Exception:
            pass
    
    # Draw Company Logo (KMC Logo spot - Static)
    if company_branding and company_branding.get('logo_bytes'):
        try:
            logo_img = ImageReader(BytesIO(company_branding['logo_bytes']))
            # Position: Next to the Signature Text
            c.drawImage(logo_img, 210, 15, width=75, height=75, mask='auto', preserveAspectRatio=True)
        except Exception:
            pass

    # --- 6. QR CODE — FIXED POSITION (inside green box) ---
    qr_size = 80
    verify_url = f"http://127.0.0.1:5500/verify.html?id={certificate_data['certificate_uid']}"
    qr = qrcode.QRCode(version=1, box_size=10, border=0)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    # Adjusted: X=736 (shifted right), Y=html_to_pdf_y(488 + 80) - 10 (lowered slightly)
    c.drawImage(ImageReader(qr_buffer), 736, html_to_pdf_y(488 + 80) - 10, width=qr_size, height=qr_size)

    # --- 7. PREVIEW WATERMARK ---
    if is_preview:
        c.saveState()
        c.translate(page_width / 2, page_height / 2)
        c.rotate(45)
        c.setFont("Helvetica-Bold", 80)
        c.setFillColor(lightgrey, alpha=0.3)
        c.drawCentredString(0, 0, "PENDING APPROVAL")
        c.restoreState()

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf