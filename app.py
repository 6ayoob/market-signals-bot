import os
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Dispatcher
from models import SessionLocal, User, Subscription, init_db
from payments import create_invoice
from config import TELEGRAM_TOKEN, ADMIN_IDS, NOWPAYMENTS_IPN_SECRET, SUBSCRIPTION_DURATION_DAYS
from datetime import datetime, timedelta
import hmac
import hashlib
import asyncio

app = Flask(__name__)

init_db()
db = SessionLocal()

# إعداد بوت التيليجرام باستخدام Long Polling مع Flask Dispatcher
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
dispatcher = application.dispatcher

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = str(user.id)
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not db_user:
        db_user = User(
            telegram_id=telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        db.add(db_user)
        db.commit()
    await update.message.reply_text(
        "مرحباً بك في بوت إشارات التداول.\n"
        "للاشتراك أرسل /subscribe\n"
        "لمعرفة حالة اشتراكك أرسل /status\n"
        "لتجديد الاشتراك أرسل /renew"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not db_user:
        await update.message.reply_text("لم يتم العثور على بياناتك. الرجاء إرسال /start أولاً.")
        return
    active_sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == db_user.id)
        .filter(Subscription.status == "active")
        .order_by(Subscription.end_date.desc())
        .first()
    )
    if active_sub and active_sub.end_date > datetime.utcnow():
        days_left = (active_sub.end_date - datetime.utcnow()).days
        await update.message.reply_text(f"اشتراكك فعال وينتهي بعد {days_left} يوم.")
    else:
        await update.message.reply_text("ليس لديك اشتراك نشط حالياً. أرسل /subscribe للاشتراك.")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    invoice = create_invoice(telegram_id)
    if invoice:
        url = invoice.get("invoice_url")
        await update.message.reply_text(
            f"يرجى دفع الاشتراك عبر الرابط التالي:\n{url}\n"
            "بعد الدفع، سيتم تفعيل اشتراكك تلقائيًا."
        )
    else:
        await update.message.reply_text("حدث خطأ أثناء إنشاء رابط الدفع، حاول لاحقًا.")

async def renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # يمكن إعادة استخدام create_invoice بنفس الطريقة
    await subscribe(update, context)

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("subscribe", subscribe))
dispatcher.add_handler(CommandHandler("renew", renew))

@app.route("/webhook/payment", methods=["POST"])
def payment_webhook():
    raw_data = request.data
    signature = request.headers.get("x-nowpayments-signature", "")

    # تحقق التوقيع
    computed = hmac.new(
        NOWPAYMENTS_IPN_SECRET.encode("utf-8"),
        raw_data,
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(computed, signature):
        return jsonify({"error": "Invalid signature"}), 400

    data = request.json
    payment_status = data.get("payment_status")
    currency = data.get("payment_currency")
    paid_amount = float(data.get("paid_amount", 0))
    price_amount = float(data.get("price_amount", 0))
    telegram_id = data.get("order_id")

    if payment_status == "finished" and currency.lower() == "usdt" and paid_amount >= price_amount:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            # تفعيل الاشتراك
            now = datetime.utcnow()
            new_sub = Subscription(
                user_id=user.id,
                status="active",
                start_date=now,
                end_date=now + timedelta(days=SUBSCRIPTION_DURATION_DAYS),
                payment_id=data.get("payment_id"),
                amount=paid_amount,
                currency=currency
            )
            db.add(new_sub)
            db.commit()
            print(f"Subscription activated for user {telegram_id}")
            return jsonify({"status": "success"}), 200

    return jsonify({"error": "Payment not valid or incomplete"}), 400

if __name__ == "__main__":
    # تشغيل Flask و Telegram معاً
    from threading import Thread

    def run_flask():
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    asyncio.run(application.run_polling())
