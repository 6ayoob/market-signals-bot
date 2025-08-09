from models import SessionLocal, User

def assign_admin(telegram_id: str):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if user:
        user.is_admin = True
        session.commit()
        print(f"تم تعيين المستخدم {telegram_id} كأدمن.")
    else:
        print(f"المستخدم {telegram_id} غير موجود في قاعدة البيانات.")
    session.close()

if __name__ == "__main__":
    telegram_id = input("أدخل معرف تيليجرام للمستخدم الذي تريد تعيينه أدمن: ").strip()
    assign_admin(telegram_id)
