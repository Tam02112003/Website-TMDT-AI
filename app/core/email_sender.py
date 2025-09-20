import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.settings import settings
from core.app_config import logger

def send_email(to_email: str, subject: str, message: str):
    msg = MIMEMultipart()
    msg['From'] = settings.SMTP.FROM
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))

    try:
        server = smtplib.SMTP(settings.SMTP.HOST, settings.SMTP.PORT)
        server.starttls()
        server.login(settings.SMTP.USER, settings.SMTP.PASSWORD.get_secret_value())
        text = msg.as_string()
        server.sendmail(settings.SMTP.FROM, to_email, text)
        server.quit()
        logger.info(f"Email sent successfully to {to_email} with subject: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)