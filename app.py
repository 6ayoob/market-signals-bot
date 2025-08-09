import os
import json
from datetime import datetime, timedelta

from flask import Flask, request, jsonify
import requests
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# إعدادات أساسية
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ضع_توكن_البوت_هنا")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
NOWPAYMENTS_IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET", "ضع_IPN_SECRET_هنا")

WEBHOOK_ROUTE = f"/market-signals-bot/telegram-webhook"
NOWPAYMENTS_ROUTE = f"/market-signals-bot/nowpayments-webhook"
PORT = int(os.getenv("PORT", 5000))

# قاعدة البيانات
DATABASE_URL = "sqlite:///./market_signals_bot.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    subscriptions = relationship("Subscription", back_populates="user")

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    status = Column(String, default="active")  # active, expired
    payment_id = Column(String, nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    user = relationship("User", back_populates="subscriptions")

Base.metadata.create_all(bind=engine)

app = Flask(__name__)

def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def get_user(session, telegram_id, create_if_not_exist=True, user_info=None):
    user = session.query(User).filter_by(telegram_id=str(telegram_id)).first()
    if not user and create_if_not_exist:
        user = User(
            telegram_id=str(telegram_id),
            username=user_info.get("username") if user_info else None,
            first_name=user_info.get("first_name") if user_info else None,
            last_name=user_info.get("last_name") if user_info else None,
        )
        session.add(user)
        session.commit()
    return user

def get_active_subscription(session, user_id):
    now = datetime.utcnow()
    return session.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status == "active",
        Subscription.start_date <= now,
        Subscription.end_date >= now
    ).first()

def expire_subscriptions():
    session = SessionLocal()
    now = datetime.utcnow()
    expired = session.query(Subscription).filter(
        Subscription.status == "active",
        Subscription.end_date < now
    ).all()
    for sub in expired:
        sub.status = "expired"
        session.add(sub)
    session.commit()
    session.close()

@app.route(WEBHOOK_ROUTE, methods=["POST"])
def telegram_webhook():
    expire_subscriptions()
    update = request.get_json()
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        from_user = message.get("from", {})
        telegram_id = str(from_user.get("id"))

        session = SessionLocal()
        user = get_user(session, telegram_id, True, from_user)
        sub = get_active_subscription(session, user.id)
        session.close()

        if not sub:
            send_message(chat_id, "🚫 يرجى الاشتراك أولاً للدخول إلى الخدمة.\n\n"\
                                 "استخدم /subscribe للاطلاع على الخطط المتاحة.")
            return "ok"

        # أوامر البوت
        if text == "/start":
            send_message(chat_id, f"مرحبًا {user.first_name or ''} 👋\n"
                                  "البوت يعمل بنجاح.\n"
                                  "استخدم /help لمعرفة الأوامر.")
        elif text == "/help":
            send_message(chat_id,
                "/subscribe - الاشتراك في الخدمة\n"
                "/status - حالة الاشتراك\n"
                "/advice - تلقي توصية وتحليل\n"
                "/cancel - إلغاء الاشتراك")
        elif text == "/subscribe":
            send_message(chat_id,
                "خطط الاشتراك:\n"
                "1️⃣ اشتراك 1 بسعر 40$ (استراتيجية 1)\n"
                "2️⃣ اشتراك 2 بسعر 70$ (استراتيجية 2)\n"
                "يرجى زيارة الرابط للدفع (يتم إرساله من إدارة البوت تلقائيًا بعد طلب الاشتراك).")
        elif text == "/status":
            send_message(chat_id,
                         f"حالة اشتراكك:\n"
                         f"من: {sub.start_date.strftime('%Y-%m-%d')}\n"
                         f"إلى: {sub.end_date.strftime('%Y-%m-%d')}\n"
                         f"الحالة: {sub.status}")
        elif text == "/cancel":
            session = SessionLocal()
            sub = get_active_subscription(session, user.id)
            if sub:
                sub.status = "expired"
                session.add(sub)
                session.commit()
                send_message(chat_id, "تم إلغاء اشتراكك. شكرًا لك.")
            else:
                send_message(chat_id, "ليس لديك اشتراك نشط للإلغاء.")
            session.close()
        elif text == "/advice":
            # دمج استراتيجياتك هنا
            send_message(chat_id, "📊 لا توجد توصيات حالياً.")
        else:
            send_message(chat_id, "❓ أمر غير معروف، استخدم /help للمساعدة.")
    return "ok"

@app.route(NOWPAYMENTS_ROUTE, methods=["POST"])
def nowpayments_webhook():
    signature = request.headers.get("x-nowpayments-sig")
    if signature != NOWPAYMENTS_IPN_SECRET:
        return "Unauthorized", 401

    data = request.get_json()

    payment_status = data.get("payment_status")
    order_id = data.get("order_id")
    amount = data.get("pay_amount")
    currency = data.get("pay_currency")

    if payment_status == "finished":
        session = SessionLocal()
        user = get_user(session, str(order_id), create_if_not_exist=False)

        if not user:
            session.close()
            return jsonify({"error": "User not found"}), 404

        active_sub = get_active_subscription(session, user.id)
        if active_sub and active_sub.status == "active":
            session.close()
            return jsonify({"message": "Subscription already active"}), 200

        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=30)

        new_sub = Subscription(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
            status="active",
            payment_id=str(data.get("payment_id")),
            amount=amount,
            currency=currency
        )
        session.add(new_sub)
        session.commit()
        session.close()

        send_message(int(user.telegram_id), f"✅ تم تفعيل اشتراكك بنجاح حتى {end_date.strftime('%Y-%m-%d')}\n"
                                            f"بسم الله  !")
    return "ok"

@app.route("/")
def home():
    return "بوت market-signals-bot يعمل بنظام Webhook و NowPayments IPN."

if __name__ == "__main__":
    print("تشغيل بوت market-signals-bot...")
    app.run(host="0.0.0.0", port=PORT)
