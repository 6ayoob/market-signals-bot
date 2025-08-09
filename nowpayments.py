# nowpayments.py
import requests
import os
import hmac
import hashlib

from config import NOWPAYMENTS_API_KEY, NOWPAYMENTS_IPN_SECRET

NOWPAYMENTS_API_URL = "https://api.nowpayments.io/v1/invoice"

HEADERS = {
    "x-api-key": NOWPAYMENTS_API_KEY,
    "Content-Type": "application/json"
}

def create_invoice(subscription_id: int, amount_usd: float, pay_currency: str = "usdt", ipn_callback_url: str = None):
    """
    ينشئ فاتورة في NowPayments ويرجع (invoice_url, invoice_id) أو (None, None)
    subscription_id: سنستخدمه كـ order_id لربط الفاتورة بالاشتراك في DB
    """
    if ipn_callback_url is None:
        ipn_callback_url = os.getenv("NOWPAYMENTS_IPN_CALLBACK_URL")

    payload = {
        "price_amount": amount_usd,
        "price_currency": "usd",       # السعر مقيم بالدولار
        "pay_currency": pay_currency,  # العملة التي يريد الدفع بها (usdt الخ)
        "order_id": str(subscription_id),
        "order_description": f"Subscription #{subscription_id}",
        "ipn_callback_url": ipn_callback_url
    }
    try:
        resp = requests.post(NOWPAYMENTS_API_URL, headers=HEADERS, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # data يحتوي على keys مثل: id, invoice_url, etc.
        invoice_url = data.get("invoice_url")
        invoice_id = data.get("id") or data.get("invoice_id") or data.get("payment_id")
        return invoice_url, invoice_id
    except Exception as e:
        print(f"[nowpayments] create_invoice error: {e}")
        return None, None

def verify_nowpayments_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    التحقق من التوقيع: NowPayments يوقّع جسم الطلب بـ HMAC-SHA512 باستخدام NOWPAYMENTS_IPN_SECRET
    Header المتوقع: 'x-nowpayments-signature' أو ما ضبطته في حسابك
    """
    if not NOWPAYMENTS_IPN_SECRET:
        print("[nowpayments] No IPN secret configured")
        return False
    try:
        computed = hmac.new(
            NOWPAYMENTS_IPN_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(computed, signature_header)
    except Exception as e:
        print(f"[nowpayments] verify signature error: {e}")
        return False
