import requests
import os

NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
NOWPAYMENTS_API_URL = "https://api.nowpayments.io/v1/invoice"

HEADERS = {
    "x-api-key": NOWPAYMENTS_API_KEY,
    "Content-Type": "application/json"
}

def create_invoice_nowpayments(subscription_id: int, amount: float, currency: str = "USDT"):
    data = {
        "price_amount": amount,
        "price_currency": currency,
        "order_id": str(subscription_id),
        "order_description": f"Subscription payment #{subscription_id}",
        "ipn_callback_url": os.getenv("NOWPAYMENTS_IPN_CALLBACK_URL"),
        "success_url": os.getenv("NOWPAYMENTS_SUCCESS_URL"),
        "cancel_url": os.getenv("NOWPAYMENTS_CANCEL_URL"),
    }
    response = requests.post(NOWPAYMENTS_API_URL, headers=HEADERS, json=data)
    if response.status_code == 201:
        result = response.json()
        return result["invoice_url"], result["id"]
    else:
        print(f"Failed to create invoice: {response.text}")
        return None, None
