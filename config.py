import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
NOWPAYMENTS_IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET")  # تستخدم للتحقق من توقيع webhook
NOWPAYMENTS_IPN_CALLBACK_URL = os.getenv("NOWPAYMENTS_IPN_CALLBACK_URL")  # https://your-app.onrender.com/nowpayments/webhook
SUBSCRIPTION_DURATION_DAYS = int(os.getenv("SUBSCRIPTION_DURATION_DAYS", "30"))

# أسعار الاشتراكات
PRICE_STRATEGY_ONE_USD = float(os.getenv("PRICE_STRATEGY_ONE_USD", "40"))
PRICE_STRATEGY_TWO_USD = float(os.getenv("PRICE_STRATEGY_TWO_USD", "70"))
