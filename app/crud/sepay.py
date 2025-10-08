import httpx
from core.settings import settings
from core.app_config import logger

def verify_api_key(authorization_header: str | None) -> bool:
    """
    Verifies the API Key from the Authorization header for Sepay webhooks.
    """
    if not authorization_header:
        return False

    correct_token = settings.SEPAY.API_TOKEN.get_secret_value()
    expected_header = f"Apikey {correct_token}"
    return authorization_header == expected_header

def create_sepay_payment(order_id: str, amount: int):
    """
    Creates a payment request with the Sepay API.
    """
    api_url = f"{settings.SEPAY.API_URL}/transactions"
    api_token = settings.SEPAY.API_TOKEN.get_secret_value()
    headers = {
        "Authorization": f"Apikey {api_token}",
        "Content-Type": "application/json"
    }
    # NOTE: The payload structure is an assumption based on common API patterns.
    # You may need to adjust fields like 'redirectUrl' based on official Sepay documentation.
    payload = {
        "referenceCode": order_id,
        "amount": amount,
        "description": f"Payment for order {order_id}",
        "redirectUrl": f"{settings.FRONTEND.URL}/order-result" # Assumes a generic redirect URL
    }

    logger.info(f"Sending payment creation request to Sepay for order {order_id}")

    try:
        with httpx.Client() as client:
            response = client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
            
            sepay_response = response.json()
            logger.info(f"Sepay payment creation successful: {sepay_response}")
            return sepay_response

    except httpx.HTTPStatusError as e:
        logger.error(f"Sepay API request failed with status {e.response.status_code}: {e.response.text}", exc_info=True)
        # Re-raise or handle specific errors
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating Sepay payment: {e}", exc_info=True)
        raise
