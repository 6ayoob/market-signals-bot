from models import User, Subscription
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

def get_or_create_user(db: Session, telegram_id: str, username=None, first_name=None, last_name=None):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def create_subscription(db: Session, telegram_id: str, strategy: str, amount: float, currency: str = "USDT"):
    user = get_or_create_user(db, telegram_id)
    subscription = Subscription(
        user_id=user.id,
        strategy=strategy,
        amount=amount,
        currency=currency,
        status="pending",
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription

def activate_subscription(db: Session, payment_id: str):
    subscription = db.query(Subscription).filter(Subscription.payment_id == payment_id).first()
    if subscription and subscription.status != "active":
        subscription.status = "active"
        subscription.start_date = datetime.utcnow()
        subscription.end_date = datetime.utcnow() + timedelta(days=30)
        db.commit()
        return subscription
    return None

def get_active_subscription(db: Session, telegram_id: str):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return None
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id)
        .filter(Subscription.status == "active")
        .filter(Subscription.end_date >= datetime.utcnow())
        .order_by(Subscription.end_date.desc())
        .first()
    )
    return subscription

def get_user_strategy(db: Session, telegram_id: str):
    subscription = get_active_subscription(db, telegram_id)
    if subscription:
        return subscription.strategy
    return None
