from core.settings import settings
from core.app_config import logger
from twilio.rest import Client
import phonenumbers # Import phonenumbers

async def send_sms(to_phone_number: str, message: str):
    """
    Sends an SMS using Twilio, with robust phone number validation and formatting.
    """
    try:
        account_sid = settings.SMS.ACCOUNT_SID.get_secret_value()
        auth_token = settings.SMS.AUTH_TOKEN.get_secret_value()
        twilio_phone_number = settings.SMS.SENDER_ID

        # Parse and validate the phone number
        try:
            parsed_number = phonenumbers.parse(to_phone_number, settings.SMS.DEFAULT_COUNTRY_CODE.replace('+', '')) # Pass default region
            if not phonenumbers.is_valid_number(parsed_number):
                raise ValueError("Invalid phone number.")
            to_phone_number_e164 = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
        except Exception as e:
            logger.error(f"Phone number parsing/validation failed for {to_phone_number}: {e}", exc_info=True)
            raise ValueError(f"Invalid phone number format: {to_phone_number}")

        client = Client(account_sid, auth_token)

        message_instance = client.messages.create(
            to=to_phone_number_e164,
            from_=twilio_phone_number,
            body=message
        )
        logger.info(f"SMS sent successfully to {to_phone_number}. SID: {message_instance.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SMS to {to_phone_number} using Twilio: {e}", exc_info=True)
        return False
