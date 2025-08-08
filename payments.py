import requests
import os
from config import NOWPAYMENTS_API_KEY, SUBSCRIPTION_PRICE_USD

NOWPAYMENTS_API_URL = "https://api.nowpayments.io/v1/invoice"

headers = {
    "x-api-key": NOWPAYMENTS_API_KEY,
    "Content-Type": "application/json"
}

def create_invoice(telegram_id: str):
    data = {
        "price_amount": SUBSCRIPTION_PRICE_USD,
        "price_currency": "usd",
        "pay_currency": "usdt",
        "ipn_callback_url": os.getenv("IPN_CALLBACK_URL"),  # رابط Webhook عندك
        "order_id": telegram_id,  # نستخدم معرف تيليجرام لربط الدفع بالمستخدم
        "order_description": "اشتراك بوت إشارات التداول لمدة 30 يوم"
    }
    response = requests.post(NOWPAYMENTS_API_URL, json=data, headers=headers)
    if response.status_code == 201:
        return response.json()  # تحتوي على رابط الدفع invoice_url وغيره
    else:
        return None
