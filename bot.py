from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from config import TELEGRAM_TOKEN, ADMIN_IDS
from models import SessionLocal, User, Subscription, init_db
from datetime import datetime, timedelta

init_db()  # إنشاء الجداول عند بداية التشغيل

db = SessionLocal()

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
        "للحالة الحالية أرسل /status\n"
        "لتجديد الاشتراك أرسل /renew"
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    # هنا سترسل رابط دفع مع فاتورة، لاحقاً نكمل الكود
    await update.message.reply_text(
        "سيتم إرسال رابط الدفع بعد إعداد بوابة الدفع."
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

# تابع باقي أوامر الإدارة لاحقاً
