"""
Запуск GUI версии FastPanel Automation
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

def check_requirements():
    """Проверка установленных зависимостей"""
    required_modules = {
        'customtkinter': 'customtkinter',
        'paramiko': 'paramiko',
        'PIL': 'Pillow'
    }
    
    missing = []
    for module, package in required_modules.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("❌ Не установлены необходимые зависимости:")
        print(f"   Выполните: pip install {' '.join(missing)}")
        print(f"   Или: pip install -r requirements.txt")
        return False
    
    return True

def create_directories():
    """Создание необходимых директорий"""
    dirs = ['data', 'logs']
    for dir_name in dirs:
        dir_path = ROOT_DIR / dir_name
        dir_path.mkdir(exist_ok=True)

def main():
    """Главная функция запуска"""
    print("🚀 FastPanel Automation - GUI Version")
    print("-" * 40)
    
    # Проверяем зависимости
    if not check_requirements():
        sys.exit(1)
    
    # Создаем директории
    create_directories()
    
    # Импортируем и запускаем приложение
    try:
        from src.ui.app import FastPanelApp
        
        print("✅ Запуск графического интерфейса...")
        print("-" * 40)
        
        app = FastPanelApp()
        app.mainloop()
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("   Убедитесь, что файл src/ui/app.py существует")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
