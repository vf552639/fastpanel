"""
Конфигурация приложения
"""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Базовые пути
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Создаем директории если их нет
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

@dataclass
class AppConfig:
    """Основные настройки приложения"""
    # Пути
    servers_file: Path = DATA_DIR / "servers.json"
    credentials_file: Path = DATA_DIR / "credentials.json"
    log_file: Path = LOGS_DIR / "automation.log"
    
    # SSH настройки по умолчанию
    ssh_timeout: int = 30
    ssh_port: int = 22
    ssh_user: str = "root"
    
    # FastPanel
    fastpanel_install_url: str = "http://fastpanel.direct/install_ru.sh"
    fastpanel_admin_port: int = 8888
    
    # Cloudflare (для будущего расширения)
    cloudflare_api_url: str = "https://api.cloudflare.com/client/v4"
    
    # UI настройки
    app_name: str = "FastPanel Automation"
    app_version: str = "0.1.0 MVP"
    
    # Безопасность
    encryption_enabled: bool = False  # Отключено для MVP
    
    # Режим отладки
    debug: bool = True

# Глобальный экземпляр конфигурации
config = AppConfig()

# Переменные окружения (если нужно переопределить)
if os.getenv("FP_DEBUG"):
    config.debug = os.getenv("FP_DEBUG").lower() == "true"

if os.getenv("FP_SSH_TIMEOUT"):
    config.ssh_timeout = int(os.getenv("FP_SSH_TIMEOUT"))
