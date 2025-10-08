from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from core.settings import settings
from core.app_config import logger
from datetime import datetime

def send_email(to_email: str, subject: str, order_details: dict):
    try:
        # Extract details for plain text and HTML
        user_name = order_details.get('user_name', 'Customer')
        order_code = order_details.get('order_code', 'N/A')
        total_amount = order_details.get('total_amount', 0.0)
        payment_method = order_details.get('payment_method', 'N/A')
        order_status = order_details.get('order_status', 'N/A')
        shipping_address = order_details.get('shipping_address', {})
        items = order_details.get('items', [])
        order_date = order_details.get('order_date', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')

        # Generate Plain Text Message
        plain_message = f"""Dear {user_name},

            Your order {order_code} has been {order_status.lower()} successfully.
            
            Order Details:
            Order Code: {order_code}
            Order Date: {order_date}
            Total Amount: {total_amount:,.2f} VND
            Payment Method: {payment_method}
            Status: {order_status}
            
            Shipping Address:
            {shipping_address.get('address', 'N/A')}, {shipping_address.get('city', 'N/A')}, {shipping_address.get('postal_code', 'N/A')}, {shipping_address.get('country', 'N/A')}
            Phone: {shipping_address.get('phone_number', 'N/A')}

        Items:
        """
        for item in items:
            plain_message += f"- {item.get('product_name', 'N/A')} (x{item.get('quantity', 1)}) - {item.get('price', 0.0):,.2f} VND\n"
        plain_message += f"""
        Thank you for your purchase!
        
        Best regards,
        MinhTam AI Shop
        """

        # Generate HTML Message
        items_html = ""
        for item in items:
            items_html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">{item.get('product_name', 'N/A')}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{item.get('quantity', 1)}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{item.get('price', 0.0):,.2f} VND</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{(item.get('quantity', 1) * item.get('price', 0.0)):,.2f} VND</td>
            </tr>
            """

        html_message = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{subject}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
                    .header {{ background-color: #f8f8f8; padding: 20px; text-align: center; border-bottom: 1px solid #ddd; }}
                    .header img {{ max-width: 150px; height: auto; }}
                    .content {{ padding: 20px 0; }}
                    .footer {{ margin-top: 20px; padding-top: 10px; border-top: 1px solid #ddd; text-align: center; font-size: 0.9em; color: #777; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    th, td {{ padding: 8px; border: 1px solid #ddd; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    .total {{ text-align: right; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <!-- Replace with your logo URL -->
                        <img src="https://res.cloudinary.com/dafssc4je/image/upload/v1759937015/manual_uploads/arymwqqsanix1z26cryj.png" alt="MinhTam AI Shop Logo">
                        <h2>Order Confirmation</h2>
                    </div>
                    <div class="content">
                        <p>Dear {user_name},</p>
                        <p>Your order <strong>#{order_code}</strong> has been {order_status.lower()} successfully.</p>
                        <p>Thank you for your purchase!</p>
            
                        <h3>Order Summary</h3>
                        <table>
                            <tr><th>Order Code:</th><td>{order_code}</td></tr>
                            <tr><th>Order Date:</th><td>{order_date}</td></tr>
                            <tr><th>Total Amount:</th><td>{total_amount:,.2f} VND</td></tr>
                            <tr><th>Payment Method:</th><td>{payment_method}</td></tr>
                            <tr><th>Status:</th><td>{order_status}</td></tr>
                        </table>
            
                        <h3>Shipping Address</h3>
                        <p>
                            {shipping_address.get('address', 'N/A')}<br>
                            {shipping_address.get('city', 'N/A')}, {shipping_address.get('postal_code', 'N/A')}<br>
                            {shipping_address.get('country', 'N/A')}<br>
                            Phone: {shipping_address.get('phone_number', 'N/A')}
                        </p>
            
                        <h3>Items Ordered</h3>
                        <table>
                            <thead>
                                <tr>
                                    <th>Product</th>
                                    <th>Quantity</th>
                                    <th>Unit Price</th>
                                    <th>Subtotal</th>
                                </tr>
                            </thead>
                            <tbody>
                                {items_html}
                            </tbody>
                        </table>
                    </div>
                    <div class="footer">
                        <p>If you have any questions, please contact us.</p>
                        <p>&copy; {datetime.now().year} MinhTam AI Shop. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
        """

        message_obj = Mail(
            from_email=settings.SMTP.FROM,
            to_emails=to_email,
            subject=subject,
            plain_text_content=plain_message,
            html_content=html_message
        )
        sg = SendGridAPIClient(settings.SENDGRID.API_KEY.get_secret_value())
        response = sg.send(message_obj)

        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Email sent successfully to {to_email} with subject: {subject}. Status Code: {response.status_code}")
        else:
            logger.error(f"Failed to send email to {to_email}. Status Code: {response.status_code}, Body: {response.body}, Headers: {response.headers}")

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)