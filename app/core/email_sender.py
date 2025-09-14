import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.settings import settings
from core.app_config import logger

def send_email(to_email: str, subject: str, message: str):
    msg = MIMEMultipart()
    msg['From'] = settings.EMAIL.SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))

    try:
        server = smtplib.SMTP(settings.EMAIL.SMTP_SERVER, settings.EMAIL.SMTP_PORT)
        server.starttls()
        server.login(settings.EMAIL.SENDER_EMAIL, settings.EMAIL.SENDER_PASSWORD)
        text = msg.as_string()
        server.sendmail(settings.EMAIL.SENDER_EMAIL, to_email, text)
        server.quit()
        logger.info(f"Email sent successfully to {to_email} with subject: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)