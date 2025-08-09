from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, JSON, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./market_signals_bot.db"

Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)  # تم إضافة هذا الحقل
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="user")

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    strategy = Column(String, nullable=False, default="strategy_one")
    status = Column(String, default="pending")  # pending, active, expired
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    payment_id = Column(String, nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True)

    user = relationship("User", back_populates="subscriptions")

class SignalLog(Base):
    __tablename__ = "signal_logs"
    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String, nullable=True)
    symbol = Column(String, nullable=True)
    entry_price = Column(Float, nullable=True)
    tps = Column(JSON, nullable=True)
    sl = Column(Float, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    sent_to_count = Column(Integer, default=0)
    admin_id = Column(String, nullable=True)
    notes = Column(String, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)
