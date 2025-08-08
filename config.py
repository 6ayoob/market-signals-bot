import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))  # قائمة أرقام الأدمين مفصولة بفاصلة
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
NOWPAYMENTS_IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET")

SUBSCRIPTION_PRICE_USD = 60
SUBSCRIPTION_DURATION_DAYS = 30
