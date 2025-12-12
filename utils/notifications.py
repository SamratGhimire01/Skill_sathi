# backend/utils/notifications.py (FINAL VERSION with Beautiful Message)

from fastapi import BackgroundTasks
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication 
from email.mime.image import MIMEImage # <--- NEW IMPORT FOR QR CODE
import smtplib
import os
import qrcode # <--- NEW IMPORT
from io import BytesIO # <--- NEW IMPORT

# --- CRITICAL CONFIGURATION (USE YOUR GMAIL APP PASSWORD) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "samratghimire01@gmail.com"
SENDER_PASSWORD = "kcmj uuhb qrhb hqtb" 
# -----------------------------------------------------------

# --- HELPER: Generate QR Code Bytes ---
def generate_qr_png_bytes(url: str) -> bytes:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def send_email_real(to_email: str, subject: str, html_body: str, attachments: list = None):
    """Sends email using a real SMTP server with a list of attachments."""
    
    if SENDER_PASSWORD == "YOUR_GMAIL_APP_PASSWORD":
        print("\n❌ [Email Failed] SMTP password not configured! Check notifications.py.")
        return False
        
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email

        # Attach HTML body
        msg.attach(MIMEText(html_body, 'html'))
        
        # Attach all items in the list (PDF, PNG, etc.)
        if attachments:
            for data, filename, subtype in attachments:
                if subtype == 'pdf':
                    part = MIMEApplication(data, _subtype="pdf")
                elif subtype == 'png':
                    part = MIMEImage(data, _subtype="png")
                else:
                    continue
                    
                part.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(part)

        # Send via SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        
        print(f"\n📧 [Email Success] Sent to {to_email} - Subject: {subject}")
        return True
    
    except Exception as e:
        print(f"\n❌ [Email Failed] Cannot send to {to_email}. Error: {e}")
        return False

# 1. Certificate Issue Notification (To Company Admin) - No changes needed
def trigger_certificate_email(background_tasks: BackgroundTasks, company_email: str, recipient_name: str, notify_enabled: bool):
    if notify_enabled:
        subject = "New Certificate Issued"
        html_body = f"""
            <p>A new certificate has been issued to <b>{recipient_name}</b> by your staff.</p>
            <p>Please log in to your dashboard to review the audit log.</p>
            <p><a href="http://127.0.0.1:5500/dashboard.html">Go to Dashboard</a></p>
        """
        background_tasks.add_task(send_email_real, company_email, subject, html_body)

# 2. Worker Creation Notification (To New Worker) - No changes needed
def trigger_worker_onboarding(background_tasks: BackgroundTasks, worker_email: str, worker_name: str, worker_id: str, temp_password: str):
    if worker_email:
        subject = "Welcome to SkillSathi - Your Staff Portal Credentials"
        html_body = f"""
            <h3>Hello {worker_name}, Welcome to the SkillSathi Staff Portal!</h3>
            <p>Here are your login credentials:</p>
            <ul>
                <li><b>Portal Link:</b> <a href="http://127.0.0.1:5500/staff_login.html">Staff Login</a></li>
                <li><b>Your Worker ID (Username):</b> <b>{worker_id}</b></li>
                <li><b>Temporary Password:</b> <b>{temp_password}</b></li>
            </ul>
            <p style="color:red;">Please log in and change your password immediately.</p>
            """
        background_tasks.add_task(send_email_real, worker_email, subject, html_body)
        
# 3. NEW: Send Certificate to Recipient (The "Beautiful Message" Function)
# 3. Send Certificate to Recipient (The "Beautiful Message" Function)
def trigger_recipient_certificate(background_tasks: BackgroundTasks, cert_data: dict, pdf_data: bytes):
    recipient_email = cert_data.get('recipient_email')
    
    if recipient_email:
        recipient_name = cert_data.get('recipient_name', 'Valued Recipient')
        course_title = cert_data.get('course_title', 'Your Course')
        cert_uid = cert_data.get('certificate_uid')
        verify_link = f"http://127.0.0.1:5500/verify.html?id={cert_uid}"
        
        # --- 1. Generate QR Code Data ---
        qr_data = generate_qr_png_bytes(verify_link)

        subject = f"🥳 Congratulations! Your Certificate for {course_title} is Ready"
        
        # --- THE BEAUTIFUL MESSAGE ---
        html_body = f"""
            <div style="font-family:sans-serif; background:#f4f7fe; padding: 20px; border-radius: 10px;">
                <h3 style="color:#10B981;">Dear {recipient_name},</h3>
                <p>Congratulations on completing your course! Your official digital certificate (PDF) and Verification QR Code (PNG) are attached to this email.</p>
                
                <p>You can securely view and verify its authenticity online:</p>
                <p style="text-align:center;">
                    <a href="{verify_link}" style="display:inline-block; padding:10px 20px; background:#3A86FF; color:white; border-radius:5px; text-decoration:none; font-weight:bold;">
                        VIEW & VERIFY ONLINE
                    </a>
                </p>
                
                <p>Thank you for choosing our center for your training.</p>
                <p style="font-size:0.9em; color:#6B7280;">Certificate ID: {cert_uid}</p>
            </div>
        """
        
        # --- 2. Create Attachment List ---
        attachments = [
            (pdf_data, f"Certificate_{cert_uid}.pdf", 'pdf'), # PDF Attachment
            (qr_data, f"QR_Code_{cert_uid}.png", 'png')      # QR Code PNG Attachment
        ]
        
        background_tasks.add_task(
            send_email_real,
            to_email=recipient_email,
            subject=subject,
            html_body=html_body,
            attachments=attachments # Pass the list of attachments
        )