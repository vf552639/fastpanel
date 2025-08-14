"""
FastPanel Service - все операции с FastPanel
"""
import re
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from src.core.ssh_manager import SSHManager, SSHResult
from src.utils.logger import get_logger
from src.config import config

logger = get_logger("fastpanel")

@dataclass
class FastPanelInfo:
    """Информация об установленном FastPanel"""
    installed: bool
    version: Optional[str] = None
    admin_url: Optional[str] = None
    admin_password: Optional[str] = None
    install_date: Optional[str] = None
    services_status: Dict[str, bool] = None

class FastPanelService:
    """Сервис для работы с FastPanel"""
    
    def __init__(self, ssh_manager: SSHManager = None):
        self.ssh = ssh_manager or SSHManager()
    
    def check_installation(self, host: str, username: str = "root",
                          password: str = None) -> FastPanelInfo:
        """
        Проверка установлен ли FastPanel
        """
        info = FastPanelInfo(installed=False)
        
        if not self.ssh.connected:
            if not self.ssh.connect(host, username, password):
                logger.error(f"Не удалось подключиться к {host}")
                return info
        
        # Проверяем наличие FastPanel
        result = self.ssh.execute("which fastpanel")
        if result.success and result.stdout.strip():
            info.installed = True
            
            # Получаем версию
            version_result = self.ssh.execute("fastpanel --version 2>/dev/null || echo 'unknown'")
            if version_result.success:
                info.version = version_result.stdout.strip()
            
            # Формируем URL админки
            info.admin_url = f"https://{host}:{config.fastpanel_admin_port}"
            
            # Проверяем статус сервисов
            info.services_status = self._check_services()
        
        return info
    
    def install(self, host: str, username: str = "root",
               password: str = None, callback=None) -> Dict[str, Any]:
        """
        Установка FastPanel на сервер
        
        Args:
            host: IP или hostname сервера
            username: SSH пользователь
            password: SSH пароль
            callback: Функция для отслеживания прогресса
        
        Returns:
            Словарь с результатами установки
        """
        result = {
            'success': False,
            'admin_url': None,
            'admin_password': None,
            'error': None,
            'install_time': None
        }
        
        try:
            # Подключаемся если еще не подключены
            if not self.ssh.connected:
                if not self.ssh.connect(host, username, password):
                    result['error'] = "Не удалось подключиться по SSH"
                    return result
            
            # Проверяем не установлен ли уже
            check = self.check_installation(host, username, password)
            if check.installed:
                result['error'] = "FastPanel уже установлен"
                result['admin_url'] = check.admin_url
                return result
            
            logger.info(f"Начинаем установку FastPanel на {host}")
            
            # Обновляем систему (опционально для MVP)
            if callback:
                callback("📦 Обновление системы...")
            
            update_result = self.ssh.execute("apt-get update -qq", timeout=60)
            if not update_result.success:
                logger.warning("Не удалось обновить apt репозитории")
            
            # Скачиваем и запускаем установщик
            if callback:
                callback("📥 Загрузка установщика FastPanel...")
            
            install_cmd = f"wget -O - {config.fastpanel_install_url} | bash -"
            
            start_time = datetime.now()
            
            # Выполняем установку с отслеживанием прогресса
            admin_password = None
            
            def parse_output(line: str):
                nonlocal admin_password
                if callback:
                    callback(f"  {line[:80]}...")  # Обрезаем длинные строки
                
                # Ищем пароль администратора в выводе
                if "admin password" in line.lower() or "пароль администратора" in line.lower():
                    # Пытаемся извлечь пароль
                    parts = line.split(":")
                    if len(parts) > 1:
                        potential_password = parts[-1].strip()
                        if potential_password and len(potential_password) > 6:
                            admin_password = potential_password
                            logger.info(f"Найден пароль администратора")
                
                # Альтернативные паттерны для пароля
                password_match = re.search(r'password:\s*(\S+)', line, re.IGNORECASE)
                if password_match:
                    admin_password = password_match.group(1)
            
            install_result = self.ssh.execute_with_progress(install_cmd, parse_output)
            
            if install_result.success:
                result['success'] = True
                result['admin_url'] = f"https://{host}:{config.fastpanel_admin_port}"
                result['admin_password'] = admin_password or self._get_admin_password()
                result['install_time'] = (datetime.now() - start_time).total_seconds()
                
                logger.info(f"FastPanel успешно установлен на {host}")
                
                if callback:
                    callback("✅ Установка завершена успешно!")
            else:
                result['error'] = f"Установка завершилась с ошибкой: {install_result.stderr}"
                logger.error(f"Ошибка установки FastPanel: {install_result.stderr}")
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Неожиданная ошибка при установке: {e}", exc_info=True)
        
        return result
    
    def create_site(self, domain: str, site_type: str = "php",
                   php_version: str = "8.1") -> bool:
        """
        Создание нового сайта в FastPanel
        """
        if not self.ssh.connected:
            logger.error("Нет активного SSH подключения")
            return False
        
        try:
            # Команда создания сайта (зависит от версии FastPanel)
            cmd = f"fastpanel site create --domain {domain} --type {site_type}"
            
            if site_type == "php":
                cmd += f" --php {php_version}"
            
            result = self.ssh.execute(cmd)
            
            if result.success:
                logger.info(f"Сайт {domain} успешно создан")
                return True
            else:
                logger.error(f"Ошибка создания сайта: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при создании сайта: {e}")
            return False
    
    def _check_services(self) -> Dict[str, bool]:
        """
        Проверка статуса сервисов FastPanel
        """
        services = {}
        service_names = ['nginx', 'mysql', 'php-fpm', 'fastpanel']
        
        for service in service_names:
            result = self.ssh.execute(f"systemctl is-active {service}")
            services[service] = result.stdout.strip() == "active"
        
        return services
    
    def _get_admin_password(self) -> Optional[str]:
        """
        Попытка получить пароль администратора из конфигов
        """
        # Пробуем разные способы получения пароля
        locations = [
            "/usr/local/fastpanel/conf/admin.passwd",
            "/root/.fastpanel_password",
            "/etc/fastpanel/admin.password"
        ]
        
        for location in locations:
            result = self.ssh.execute(f"cat {location} 2>/dev/null")
            if result.success and result.stdout.strip():
                return result.stdout.strip()
        
        # Если не нашли, генерируем команду сброса
        logger.warning("Не удалось найти пароль администратора, требуется сброс")
        return None
    
    def reset_admin_password(self) -> Optional[str]:
        """
        Сброс пароля администратора FastPanel
        """
        if not self.ssh.connected:
            return None
        
        try:
            # Команда сброса пароля (может отличаться в разных версиях)
            result = self.ssh.execute("fastpanel admin password reset")
            
            if result.success:
                # Пытаемся извлечь новый пароль из вывода
                for line in result.stdout.split('\n'):
                    if 'password' in line.lower():
                        parts = line.split(':')
                        if len(parts) > 1:
                            return parts[-1].strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка сброса пароля: {e}")
            return None
