import hashlib
import hmac
import urllib.parse
import datetime
from core.settings import settings

class VNPay:
    def __init__(self):
        self.tmn_code = settings.VNPAY.TMN_CODE
        self.hash_secret = settings.VNPAY.HASH_SECRET.get_secret_value()
        self.vnp_url = settings.VNPAY.ENDPOINT
        self.return_url = settings.VNPAY.RETURN_URL

    def generate_payment_url(self, order_id: str, amount: int, order_desc: str, ip_addr: str, bank_code: str = None, language: str = "vn"):
        vnp_params = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'pay',
            'vnp_TmnCode': self.tmn_code,
            'vnp_Amount': amount * 100,  # VNPay requires amount in cents
            'vnp_CurrCode': 'VND',
            'vnp_TxnRef': order_id,
            'vnp_OrderInfo': order_desc,
            'vnp_OrderType': 'other',
            'vnp_Locale': language,
            'vnp_ReturnUrl': self.return_url,
            'vnp_IpAddr': ip_addr,
            'vnp_CreateDate': datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        }

        if bank_code:
            vnp_params['vnp_BankCode'] = bank_code

        # Sort parameters alphabetically
        sorted_params = sorted(vnp_params.items())

        # Create query string
        query_string = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)

        # Generate HmacSHA512 signature
        h = hmac.new(self.hash_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha512)
        vnp_SecureHash = h.hexdigest()

        payment_url = f"{self.vnp_url}?{query_string}&vnp_SecureHash={vnp_SecureHash}"
        return payment_url

    def verify_callback(self, vnp_response_data: dict):
        # Extract vnp_SecureHash and remove it from data for verification
        vnp_SecureHash = vnp_response_data.pop('vnp_SecureHash', None)
        if not vnp_SecureHash:
            return False, "Invalid signature (missing vnp_SecureHash)"

        # Sort parameters alphabetically
        sorted_params = sorted(vnp_response_data.items())

        # Create query string
        query_string = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)

        # Generate HmacSHA512 signature
        h = hmac.new(self.hash_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha512)
        my_SecureHash = h.hexdigest()

        if my_SecureHash == vnp_SecureHash:
            return True, "Signature verified"
        else:
            return False, "Invalid signature (mismatch)"

vnpay_client = VNPay()
