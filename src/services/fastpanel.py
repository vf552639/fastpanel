"""
FastPanel Service - все операции с FastPanel
"""
import re
import secrets
import string
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from src.core.ssh_manager import SSHManager
from src.utils.logger import get_logger
from src.config import config

logger = get_logger("fastpanel")


def generate_password(length=12):
    """Генерирует надежный пароль."""
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

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

    def __init__(self, ssh_manager: SSHManager = None, fastpanel_path: Optional[str] = None):
        self.ssh = ssh_manager or SSHManager()
        self.fastpanel_path_override = fastpanel_path
        self.fastpanel_path = None

    def _get_fastpanel_path(self) -> Optional[str]:
        """Определяет путь к исполняемому файлу fastpanel, отдавая приоритет настройкам."""
        if self.fastpanel_path:
            return self.fastpanel_path

        # 1. Приоритет: путь из настроек
        if self.fastpanel_path_override:
            logger.info(f"Используется путь из настроек: {self.fastpanel_path_override}")
            check_result = self.ssh.execute(f"test -f {self.fastpanel_path_override}")
            if check_result.success:
                self.fastpanel_path = self.fastpanel_path_override
                return self.fastpanel_path
            else:
                logger.error(f"Файл не найден по указанному в настройках пути: {self.fastpanel_path_override}")
                # Продолжаем поиск, чтобы попытаться найти автоматически
        
        # 2. Поиск через which
        result = self.ssh.execute("which fastpanel")
        if result.success and result.stdout.strip():
            self.fastpanel_path = result.stdout.strip()
            logger.info(f"Утилита 'fastpanel' найдена здесь: {self.fastpanel_path}")
            return self.fastpanel_path
        
        # 3. Попытка найти в стандартном месте
        fallback_path = "/usr/local/fastpanel2/app/bin/fastpanel"
        result = self.ssh.execute(f"test -f {fallback_path} && echo {fallback_path}")
        if result.success and result.stdout.strip() == fallback_path:
            self.fastpanel_path = fallback_path
            logger.info(f"Утилита 'fastpanel' найдена по стандартному пути: {self.fastpanel_path}")
            return self.fastpanel_path

        logger.error("Критическая ошибка: Не удалось найти исполняемый файл 'fastpanel' на сервере.")
        return None


    def create_site(self, domain: str, php_version: str = "7.4") -> Dict[str, Any]:
        """Создает сайт в FastPanel и верифицирует путь."""
        fp_path = self._get_fastpanel_path()
        if not fp_path: return {"success": False, "error": "Не удалось найти утилиту fastpanel на сервере. Проверьте путь в Настройках."}

        site_user = "user_" + domain.split('.')[0].replace('-', '_')
        cmd = f"{fp_path} sites create --server-name='{domain}' --owner='{site_user}' --create-user --php-version='{php_version}'"
        
        logger.info(f"Выполнение команды создания сайта: {cmd}")
        result = self.ssh.execute(cmd)

        if not result.success:
            logger.error(f"Ошибка создания сайта {domain}: {result.stderr}")
            return {"success": False, "error": result.stderr}
        
        # Верификация пути
        expected_path = f"/var/www/{site_user}/data/www/{domain}"
        check_result = self.ssh.execute(f"test -d {expected_path}")
        
        if not check_result.success:
            error_msg = f"Сайт создан, но не найден по ожидаемому пути: {expected_path}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        return {"success": True, "site_user": site_user, "path": expected_path}


    def create_ftp_account(self, domain: str) -> Dict[str, Any]:
        """Создает FTP-аккаунт для сайта."""
        fp_path = self._get_fastpanel_path()
        if not fp_path: return {"success": False, "error": "fastpanel not found"}
        
        login = "ftp_" + domain.split('.')[0].replace('-', '_')
        password = generate_password()
        cmd = f"{fp_path} ftp_account create --login='{login}' --password='{password}' --site='{domain}'"
        logger.info("Выполнение команды создания FTP-аккаунта...")
        result = self.ssh.execute(cmd)

        if result.success:
            return {"success": True, "login": login, "password": password}
        else:
            logger.error(f"Ошибка создания FTP для {domain}: {result.stderr}")
            return {"success": False, "error": result.stderr}

    def issue_ssl_certificate(self, domain: str, email: str) -> Dict[str, Any]:
        """Выпускает SSL-сертификат Let's Encrypt."""
        fp_path = self._get_fastpanel_path()
        if not fp_path: return {"success": False, "error": "fastpanel not found"}
        
        cmd = f"{fp_path} certificates create-le --server-name='{domain}' --email='{email}'"
        logger.info("Попытка выпуска SSL-сертификата...")
        result = self.ssh.execute(cmd)

        if result.success:
            return {"success": True}
        else:
            logger.warning(f"Не удалось выпустить SSL для {domain}: {result.stderr}")
            return {"success": False, "error": result.stderr}

    def run_domain_automation(self, domain_info: dict, server_credentials: dict, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Выполняет полную автоматизацию для одного домена, используя существующее SSH-соединение."""
        domain = domain_info['domain']
        updated_domain_data = domain_info.copy()

        def report_progress(message):
            if progress_callback:
                progress_callback(f"[{domain}] {message}")

        try:
            # 1. Создание сайта
            report_progress("Шаг 1: Создание сайта...")
            site_result = self.create_site(domain)
            if not site_result['success']:
                report_progress(f"ОШИБКА: Не удалось создать сайт. {site_result.get('error', '')}")
                return updated_domain_data
            
            updated_domain_data['site_user'] = site_result['site_user']
            report_progress(f"Сайт успешно создан. Пользователь: {site_result['site_user']}")
            report_progress(f"Путь к сайту: {site_result['path']}")


            # 2. Создание FTP
            report_progress("Шаг 2: Создание FTP-аккаунта...")
            ftp_result = self.create_ftp_account(domain)
            if ftp_result['success']:
                updated_domain_data['ftp_user'] = ftp_result['login']
                updated_domain_data['ftp_password'] = ftp_result['password']
                report_progress("FTP-аккаунт успешно создан.")
            else:
                report_progress(f"ПРЕДУПРЕЖДЕНИЕ: Не удалось создать FTP-аккаунт. {ftp_result.get('error', '')}")

            # 3. Выпуск SSL
            report_progress("Шаг 3: Выпуск SSL-сертификата...")
            ssl_result = self.issue_ssl_certificate(domain, f"admin@{domain}")
            if ssl_result['success']:
                updated_domain_data['ssl_status'] = 'active'
                report_progress("SSL-сертификат успешно выпущен.")
            else:
                updated_domain_data['ssl_status'] = 'error'
                report_progress(f"ПРЕДУПРЕЖДЕНИЕ: Ошибка выпуска SSL. {ssl_result.get('error', '')}")

        except Exception as e:
            report_progress(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
            logger.error(f"Критическая ошибка при автоматизации домена {domain}: {e}", exc_info=True)
            
        return updated_domain_data
