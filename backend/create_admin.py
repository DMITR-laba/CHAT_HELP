#!/usr/bin/env python3
"""
Скрипт для создания администратора
"""
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent))

from models import get_db
from models.database import User
from models.schemas import UserCreate
from services.database_service import DatabaseService
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_admin():
    """Создает администратора"""
    db = next(get_db())
    db_service = DatabaseService(db)
    
    # Проверяем, существует ли уже админ
    existing_admin = db_service.get_user_by_email("admin@example.com")
    if existing_admin:
        print("✅ Администратор уже существует:")
        print(f"   Email: {existing_admin.email}")
        print(f"   Role: {existing_admin.role}")
        return
    
    # Создаем админа
    user_data = UserCreate(
        email="admin@example.com",
        full_name="Admin",
        password="admin123",
        role="admin"
    )
    
    hashed_password = pwd_context.hash(user_data.password)
    admin = db_service.create_user(user_data, hashed_password=hashed_password, role="admin")
    
    print("✅ Администратор создан:")
    print(f"   Email: {admin.email}")
    print(f"   Password: admin123")
    print(f"   Role: {admin.role}")

if __name__ == "__main__":
    create_admin()



