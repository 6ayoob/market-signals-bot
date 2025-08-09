import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from models import SessionLocal, User, Subscription
from datetime import datetime
import strategy_one  # ملف الاستراتيجية 1، فيه check_signal(symbol)
import strategy_two  # ملف الاستراتيجية 2، فيه check_signal(symbol)

# دالة لجلب الاشتراك النشط للمستخدم من DB
def get_active_subscription(session, telegram_id: str):
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        return None
    sub = session.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.status == "active",
        Subscription.start_date <= datetime.utcnow(),
        Subscription.end_date >= datetime.utcnow()
    ).first()
    return sub

def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("اشتراك 1 - $40", callback_data='strategy_one')],
        [InlineKeyboardButton("اشتراك 2 - $70", callback_data='strategy_two')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('أهلاً! اختر الاشتراك المناسب لك:', reply_markup=reply_markup)

def subscription_choice(update: Update, context: CallbackContext):
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

        # منع الاشتراك المتكرر (pending أو active)
        existing_sub = session.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.status.in_(["pending", "active"])
        ).first()

        if existing_sub:
            query.answer()
            query.edit_message_text("لديك اشتراك مفتوح أو قيد الانتظار، يرجى إتمام الدفع أو انتظار انتهاء الاشتراك.")
            return

        new_sub = Subscription(
            user_id=user.id,
            status="pending",  # ينتظر الدفع
            start_date=None,
            end_date=None,
            payment_id=None,
            amount=40 if chosen == "strategy_one" else 70,
            currency="USD"
        )
        session.add(new_sub)
        session.commit()
    finally:
        session.close()

    query.answer()
    query.edit_message_text(f"اخترت {chosen}، سيتم إرسال رابط الدفع قريبًا.")

def analysis(update: Update, context: CallbackContext):
    telegram_id = str(update.effective_user.id)
    session = SessionLocal()
    try:
        subscription = get_active_subscription(session, telegram_id)
    finally:
        session.close()

    if not subscription:
        update.message.reply_text("ليس لديك اشتراك نشط، يرجى الاشتراك أولاً.")
        return

    messages = []
    # استبدل هذه الرموز بالقائمة الحقيقية أو قواعد بيانات المشروع
    symbols = ["BTC-USDT", "ETH-USDT", "XRP-USDT"]

    if subscription.amount == 40:
        for symbol in symbols:
            if strategy_one.check_signal(symbol):
                messages.append(f"📈 توصية شراء لـ {symbol} (استراتيجية 1)")
    else:
        for symbol in symbols:
            if strategy_two.check_signal(symbol):
                messages.append(f"🚀 توصية شراء لـ {symbol} (استراتيجية 2)")

    if messages:
        for msg in messages:
            update.message.reply_text(msg)
    else:
        update.message.reply_text("لا توجد توصيات حالياً.")

def status(update: Update, context: CallbackContext):
    telegram_id = str(update.effective_user.id)
    session = SessionLocal()
    try:
        subscription = get_active_subscription(session, telegram_id)
    finally:
        session.close()

    if subscription:
        text = (
            f"اشتراكك: {'اشتراك 1' if subscription.amount == 40 else 'اشتراك 2'}\n"
            f"الحالة: {subscription.status}\n"
            f"ينتهي في: {subscription.end_date.strftime('%Y-%m-%d') if subscription.end_date else 'غير محدد'}"
        )
    else:
        text = "لا يوجد اشتراك نشط حالياً."

    update.message.reply_text(text)

def help_command(update: Update, context: CallbackContext):
    text = (
        "/start - بدء الاشتراك\n"
        "/analysis - استلام التوصيات\n"
        "/status - حالة الاشتراك\n"
        "/help - عرض المساعدة"
    )
    update.message.reply_text(text)

def main():
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        print("خطأ: لم يتم تعيين متغير TELEGRAM_TOKEN")
        return

    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(subscription_choice))
    dp.add_handler(CommandHandler("analysis", analysis))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("help", help_command))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
