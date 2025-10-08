import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from core.settings import settings
from core.app_config import logger

def send_email(to_email: str, subject: str, message: str):
    try:
        message_obj = Mail(
            from_email=settings.SMTP.FROM,
            to_emails=to_email,
            subject=subject,
            plain_text_content=message
        )
        sg = SendGridAPIClient(settings.SENDGRID.API_KEY.get_secret_value())
        response = sg.send(message_obj)

        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Email sent successfully to {to_email} with subject: {subject}. Status Code: {response.status_code}")
        else:
            logger.error(f"Failed to send email to {to_email}. Status Code: {response.status_code}, Body: {response.body}, Headers: {response.headers}")

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)