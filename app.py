import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from sqlalchemy.orm import Session
from models import SessionLocal, init_db
from services import get_or_create_user, create_subscription, get_active_subscription, get_user_strategy, activate_subscription
from payments import create_invoice_nowpayments
import strategy_one
import strategy_two
from flask import Flask, request, jsonify
import threading
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)

# تهيئة قاعدة البيانات
init_db()

app = Flask(__name__)

SUBSCRIPTION_PLANS = {
    "strategy_one": {"price": 40, "desc": "اشتراك 1 - استراتيجية 1"},
    "strategy_two": {"price": 70, "desc": "اشتراك 2 - استراتيجية 2"},
}

WELCOME_MESSAGES = {
    "strategy_one": "أهلًا بك في اشتراك استراتيجية 1! نصيحة اليوم: تابع السوق وكن صبورًا.",
    "strategy_two": "مرحبًا في اشتراك استراتيجية 2! تذكر دائماً إدارة المخاطر وتحديد وقف الخسارة.",
}

def start(update: Update, context: CallbackContext):
    db: Session = SessionLocal()
    telegram_user = update.effective_user
    user = get_or_create_user(db, str(telegram_user.id), telegram_user.username, telegram_user.first_name, telegram_user.last_name)

    keyboard = [
        [InlineKeyboardButton(f"{plan['desc']} - ${plan['price']}", callback_data=key)]
        for key, plan in SUBSCRIPTION_PLANS.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("اختر الاشتراك المناسب لك:", reply_markup=reply_markup)
    db.close()

def subscription_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    db: Session = SessionLocal()
    user_id = str(query.from_user.id)
    chosen_plan = query.data

    subscription = create_subscription(db, user_id, chosen_plan, SUBSCRIPTION_PLANS[chosen_plan]['price'])

    invoice_url, payment_id = create_invoice_nowpayments(subscription.id, SUBSCRIPTION_PLANS[chosen_plan]['price'])
    if invoice_url:
        subscription.payment_id = payment_id
        db.commit()
        query.answer()
        query.edit_message_text(text=f"لإتمام الدفع، يرجى زيارة الرابط التالي:\n{invoice_url}")
    else:
        query.answer()
        query.edit_message_text(text="حدث خطأ أثناء إنشاء الفاتورة، حاول لاحقاً.")
    db.close()

def analysis(update: Update, context: CallbackContext):
    db: Session = SessionLocal()
    telegram_id = str(update.effective_user.id)
    strategy = get_user_strategy(db, telegram_id)
    db.close()

    if not strategy:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="لم يتم العثور على اشتراك نشط. يرجى الاشتراك أولاً.")
        return

    symbols = ["BTC-USDT", "ETH-USDT", "XRP-USDT"]
    messages = []
    for symbol in symbols:
        if strategy == "strategy_one" and strategy_one.check_signal(symbol):
            messages.append(f"📈 توصية شراء لـ {symbol} (استراتيجية 1)")
        elif strategy == "strategy_two" and strategy_two.check_signal(symbol):
            messages.append(f"🚀 توصية شراء لـ {symbol} (استراتيجية 2)")

    if messages:
        for msg in messages:
            context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="لا توجد توصيات حالياً.")

def send_welcome_message(bot, telegram_id, strategy):
    text = WELCOME_MESSAGES.get(strategy, "أهلاً بك في بوت التداول. يرجى الاشتراك لتلقي الإشارات.")
    bot.send_message(chat_id=telegram_id, text=text)

@app.route('/nowpayments/webhook', methods=['POST'])
def nowpayments_webhook():
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400

    payment_id = data.get("id")
    payment_status = data.get("payment_status")
    order_id = data.get("order_id")

    if payment_status == "finished" and order_id:
        db: Session = SessionLocal()
        subscription = activate_subscription(db, order_id)
        if subscription:
            # إرسال ترحيب للمستخدم بعد تفعيل الاشتراك
            from telegram import Bot
            bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
            user = db.query(User).filter(User.id == subscription.user_id).first()
           
