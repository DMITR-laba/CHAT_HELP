#!/usr/bin/env python3
"""
Скрипт для обновления пароля администратора
"""
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent))

from models import get_db
from models.database import User
from services.database_service import DatabaseService
from passlib.context import CryptContext
from sqlalchemy.orm import Session

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def update_admin_password(new_password: str = "admin"):
    """Обновляет пароль администратора"""
    db: Session = next(get_db())
    db_service = DatabaseService(db)
    
    # Находим админа
    admin = db_service.get_user_by_email("admin@example.com")
    
    if not admin:
        print("❌ Администратор не найден. Создаем нового...")
        from models.schemas import UserCreate
        user_data = UserCreate(
            email="admin@example.com",
            full_name="Admin",
            password=new_password,
            role="admin"
        )
        hashed_password = pwd_context.hash(new_password)
        admin = db_service.create_user(user_data, hashed_password=hashed_password, role="admin")
        print("✅ Администратор создан:")
        print(f"   Email: {admin.email}")
        print(f"   Password: {new_password}")
        print(f"   Role: {admin.role}")
        return
    
    # Обновляем пароль
    hashed_password = pwd_context.hash(new_password)
    admin.hashed_password = hashed_password
    db.commit()
    db.refresh(admin)
    
    print("✅ Пароль администратора обновлен:")
    print(f"   Email: {admin.email}")
    print(f"   New Password: {new_password}")
    print(f"   Role: {admin.role}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Обновить пароль администратора')
    parser.add_argument('--password', '-p', default='admin', help='Новый пароль (по умолчанию: admin)')
    args = parser.parse_args()
    
    update_admin_password(args.password)

