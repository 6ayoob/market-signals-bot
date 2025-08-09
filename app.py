# app.py
import os
import threading
import json
import logging
from datetime import datetime, timedelta

from flask import Flask, request, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

from models import SessionLocal, init_db, User, Subscription
from services import get_or_create_user  # إذا عندك services.py
from nowpayments import create_invoice, verify_nowpayments_signature
from config import (
    TELEGRAM_TOKEN,
    PRICE_STRATEGY_ONE_USD,
    PRICE_STRATEGY_TWO_USD,
    SUBSCRIPTION_DURATION_DAYS
)

import strategy_one
import strategy_two

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# init DB
init_db()

# Flask app
app = Flask(__name__)

# ---------- Telegram bot handlers ----------
def start_telegram_bot():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set in env")
        return

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    def start(update, context):
        keyboard = [
            [InlineKeyboardButton("اشتراك 1 - $40", callback_data='strategy_one')],
            [InlineKeyboardButton("اشتراك 2 - $70", callback_data='strategy_two')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('أهلاً! اختر الاشتراك المناسب لك:', reply_markup=reply_markup)

    def subscription_choice(update, context):
        query = update.callback_query
        chosen = query.data
        telegram_id = str(query.from_user.id)

        session = SessionLocal()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                user = User(
                    telegram_id=telegram_id,
                    username=query.from_user.username,
                    first_name=query.from_user.first_name,
                    last_name=query.from_user.last_name
                )
                session.add(user)
                session.commit()
                session.refresh(user)

            # منع الاشتراك المتكرر (pending أو active)
            existing_sub = session.query(Subscription).filter(
                Subscription.user_id == user.id,
                Subscription.status.in_(["pending", "active"])
            ).first()

            if existing_sub:
                query.answer()
                query.edit_message_text("لديك اشتراك مفتوح أو قيد الانتظار، يرجى إتمام الدفع أو انتظار انتهاء الاشتراك.")
                return

            price = PRICE_STRATEGY_ONE_USD if chosen == "strategy_one" else PRICE_STRATEGY_TWO_USD

            new_sub = Subscription(
                user_id=user.id,
                strategy=chosen,
                status="pending",  # ينتظر الدفع
                start_date=None,
                end_date=None,
                payment_id=None,
                amount=price,
                currency="usd"
            )
            session.add(new_sub)
            session.commit()
            session.refresh(new_sub)

            # إنشاء فاتورة NowPayments (order_id = subscription.id)
            invoice_url, invoice_id = create_invoice(new_sub.id, amount_usd=price)
            if invoice_url:
                # احفظ معرف الفاتورة لربطه لاحقًا
                new_sub.payment_id = invoice_id
                session.commit()
                query.answer()
                query.edit_message_text(f"تم إنشاء فاتورة الدفع، الرجاء الدفع عبر الرابط التالي:\n{invoice_url}")
            else:
                query.answer()
                query.edit_message_text("حدث خطأ أثناء إنشاء الفاتورة، حاول لاحقًا.")
        except Exception as e:
            logger.exception("subscription_choice error")
            query.answer()
            query.edit_message_text("حدث خطأ داخلي، حاول لاحقًا.")
        finally:
            session.close()

    def analysis(update, context):
        telegram_id = str(update.effective_user.id)
        session = SessionLocal()
        try:
            sub = session.query(Subscription).join(User).filter(
                User.telegram_id == telegram_id,
                Subscription.status == "active",
                Subscription.start_date <= datetime.utcnow(),
                Subscription.end_date >= datetime.utcnow()
            ).order_by(Subscription.end_date.desc()).first()
        finally:
            session.close()

        if not sub:
            update.message.reply_text("ليس لديك اشتراك نشط، يرجى الاشتراك أولاً.")
            return

        symbols = ["BTC-USDT", "ETH-USDT", "XRP-USDT"]
        msgs = []
        if sub.strategy == "strategy_one":
            for s in symbols:
                if strategy_one.check_signal(s):
                    msgs.append(f"📈 توصية شراء لـ {s} (استراتيجية 1)")
        else:
            for s in symbols:
                if strategy_two.check_signal(s):
                    msgs.append(f"🚀 توصية شراء لـ {s} (استراتيجية 2)")

        if msgs:
            for m in msgs:
                update.message.reply_text(m)
        else:
            update.message.reply_text("لا توجد توصيات حالياً.")

    def status(update, context):
        telegram_id = str(update.effective_user.id)
        session = SessionLocal()
        try:
            sub = session.query(Subscription).join(User).filter(
                User.telegram_id == telegram_id,
                Subscription.status == "active",
                Subscription.end_date >= datetime.utcnow()
            ).order_by(Subscription.end_date.desc()).first()
        finally:
            session.close()

        if sub:
            text = (f"اشتراكك: {'اشتراك 1' if sub.strategy == 'strategy_one' else 'اشتراك 2'}\n"
                    f"الحالة: {sub.status}\n"
                    f"ينتهي في: {sub.end_date.strftime('%Y-%m-%d')}")
        else:
            text = "لا يوجد اشتراك نشط حالياً."
        update.message.reply_text(text)

    def help_cmd(update, context):
        txt = "/start - بدء الاشتراك\n/analysis - استلام التوصيات\n/status - حالة الاشتراك\n/help - مساعدة"
        update.message.reply_text(txt)

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(subscription_choice))
    dp.add_handler(CommandHandler("analysis", analysis))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("help", help_cmd))

    updater.start_polling()
    updater.idle()

# ---------- Flask Webhook ----------
@app.route("/nowpayments/webhook", methods=["POST"])
def nowpayments_webhook():
    raw = request.data
    sig = request.headers.get("x-nowpayments-signature", "")  # حسب تهيئة NowPayments
    # تحقق التوقيع
    if not verify_nowpayments_signature(raw, sig):
        logger.warning("Invalid NowPayments signature")
        return jsonify({"error": "invalid signature"}), 400

    data = request.json or {}
    payment_status = data.get("payment_status")  # e.g. "finished"
    invoice_id = data.get("id") or data.get("invoice_id") or data.get("payment_id")
    order_id = data.get("order_id")  # هو الـ subscription.id لأننا أرسلناه كـ order_id

    logger.info(f"NowPayments IPN: status={payment_status}, order_id={order_id}, invoice_id={invoice_id}")

    if payment_status == "finished" and order_id:
        session = SessionLocal()
        try:
            sub = session.query(Subscription).filter(Subscription.id == int(order_id)).first()
            if sub and sub.payment_id == invoice_id:
                # تفعل الاشتراك
                sub.status = "active"
                sub.start_date = datetime.utcnow()
                sub.end_date = datetime.utcnow() + timedelta(days=SUBSCRIPTION_DURATION_DAYS)
                session.commit()

                # إرسال رسالة ترحيب للمشترك
                try:
                    bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
                    user = session.query(User).filter(User.id == sub.user_id).first()
                    if user:
                        welcome = "تم تفعيل اشتراكك بنجاح! شكراً لدعمك — ستحصل على التوصيات الآن."
                        bot.send_message(chat_id=user.telegram_id, text=welcome)
                except Exception as e:
                    logger.exception("Failed to send welcome message")
        except Exception as e:
            logger.exception("Error processing IPN")
        finally:
            session.close()
    return jsonify({"status": "ok"}), 200

# ---------- start both ----------
if __name__ == "__main__":
    # run Flask in a thread, and Telegram bot in main thread
    t = threading.Thread(target=start_telegram_bot, daemon=True)
    t.start()
    # run flask app (bind to port 5000 or env PORT)
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
