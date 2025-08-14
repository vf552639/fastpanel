"""
Настройка логирования для приложения
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logger(
    name: str = "fastpanel_automation",
    log_file: Path = None,
    level: str = "INFO",
    console: bool = True
) -> logging.Logger:
    """
    Настройка логгера с выводом в файл и консоль
    
    Args:
        name: Имя логгера
        log_file: Путь к файлу логов
        level: Уровень логирования
        console: Выводить ли в консоль
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Обработчик для файла
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Обработчик для консоли
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        # Упрощенный формат для консоли
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger

# Глобальный логгер приложения
app_logger = None

def get_logger(name: str = None) -> logging.Logger:
    """
    Получить логгер
    
    Args:
        name: Имя модуля/компонента
    """
    global app_logger
    
    if app_logger is None:
        from src.config import config
        app_logger = setup_logger(
            "fastpanel_automation",
            log_file=config.log_file,
            level="DEBUG" if config.debug else "INFO"
        )
    
    if name:
        return logging.getLogger(f"fastpanel_automation.{name}")
    return app_logger

# Удобные функции для быстрого логирования
def log_info(message: str):
    """Логирование информационного сообщения"""
    get_logger().info(message)

def log_error(message: str, exc_info: bool = False):
    """Логирование ошибки"""
    get_logger().error(message, exc_info=exc_info)

def log_warning(message: str):
    """Логирование предупреждения"""
    get_logger().warning(message)

def log_debug(message: str):
    """Логирование отладочного сообщения"""
    get_logger().debug(message)
