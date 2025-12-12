# backend/utils/notifications.py (FINAL EMAIL SENDER)

import requests
from fastapi import BackgroundTasks

# CRITICAL: This MUST match the service name defined in docker-compose.yml
PHP_MAILER_URL = "http://php-mailer" 

def send_email_via_php_service(email_to: str, subject: str, body: str):
    """Sends email via a POST request to the PHP microservice."""
    
    payload = {
        "to": email_to,
        "subject": subject,
        "body": body
    }
    
    try:
        # The internal path for the index.php script
        response = requests.post(f"{PHP_MAILER_URL}/index.php", json=payload, timeout=10)
        response.raise_for_status() # Raise exception for bad status codes
        print(f"\n📧 [PHP Mailer Success] Sent to {email_to}")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ [PHP Mailer Failed] Error sending to {email_to}. Error: {e}")

# 1. Certificate Issue Notification (To Company Admin)
def trigger_certificate_email(background_tasks: BackgroundTasks, company_email: str, recipient_name: str, notify_enabled: bool):
    if notify_enabled:
        subject = "New Certificate Issued"
        body = f"A new certificate has been issued to {recipient_name} by your staff. Please review the audit log."
        background_tasks.add_task(
            send_email_via_php_service,
            email_to=company_email,
            subject=subject,
            body=body
        )

# 2. Worker Creation Notification (To New Worker)
def trigger_worker_onboarding(background_tasks: BackgroundTasks, worker_email: str, worker_id: str, temp_password: str):
    """Sends login credentials to a new worker/staff member."""
    if worker_email:
        subject = "Welcome to SkillSathi - Your Staff Portal Credentials"
        body = f"""
            Hello,
            
            Welcome to the SkillSathi Staff Portal for your company!
            
            Here are your login credentials:
            - **Portal Link:** http://127.0.0.1:5500/staff_login.html 
            - **Your Worker ID (Username):** {worker_id}
            - **Temporary Password:** {temp_password}
            
            Please log in and change your password immediately.
            """
        background_tasks.add_task(
            send_email_via_php_service,
            email_to=worker_email,
            subject=subject,
            body=body
        )