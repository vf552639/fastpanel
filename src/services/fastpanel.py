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
import time

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

        if self.fastpanel_path_override:
            logger.info(f"Используется путь из настроек: {self.fastpanel_path_override}")
            check_result = self.ssh.execute(f"test -f {self.fastpanel_path_override}")
            if check_result.success:
                self.fastpanel_path = self.fastpanel_path_override
                return self.fastpanel_path
            else:
                logger.error(f"Файл не найден по указанному в настройках пути: {self.fastpanel_path_override}")
        
        result = self.ssh.execute("which fastpanel")
        if result.success and result.stdout.strip():
            self.fastpanel_path = result.stdout.strip()
            logger.info(f"Утилита 'fastpanel' найдена здесь: {self.fastpanel_path}")
            return self.fastpanel_path
        
        fallback_path = "/usr/local/fastpanel2/fastpanel"
        result = self.ssh.execute(f"test -f {fallback_path} && echo {fallback_path}")
        if result.success and result.stdout.strip() == fallback_path:
            self.fastpanel_path = fallback_path
            logger.info(f"Утилита 'fastpanel' найдена по стандартному пути: {self.fastpanel_path}")
            return self.fastpanel_path

        logger.error("Критическая ошибка: Не удалось найти исполняемый файл 'fastpanel' на сервере.")
        return None

    def _check_os(self, report_callback: Callable) -> Optional[str]:
        """Проверяет ОС и возвращает тип пакетного менеджера ('apt' или 'yum')."""
        report_callback("Шаг 1: Определение операционной системы...", 0.1)
        
        os_info_result = self.ssh.execute("cat /etc/os-release")
        if not os_info_result.success:
            report_callback("❌ Не удалось определить ОС.", 1.0)
            return None

        os_info = os_info_result.stdout.lower()
        os_name_match = re.search(r'^id="?(\w+)"?', os_info, re.MULTILINE)
        os_version_match = re.search(r'^version_id="?([\d\.]+)"?', os_info, re.MULTILINE)

        if not os_name_match or not os_version_match:
            report_callback("❌ Не удалось спарсить информацию об ОС.", 1.0)
            return None

        os_name = os_name_match.group(1)
        os_version = os_version_match.group(1).split('.')[0]

        report_callback(f"Обнаружена ОС: {os_name.capitalize()} {os_version}", 0.15)

        supported_os = {
            'debian': ['9', '10', '11', '12'],
            'ubuntu': ['18', '20', '22', '24'],
            'centos': ['7'],
            'almalinux': ['8'],
            'rocky': ['8']
        }

        if os_name in supported_os and os_version in supported_os[os_name]:
            report_callback("✅ ОС поддерживается.", 0.2)
            return 'apt' if os_name in ['debian', 'ubuntu'] else 'yum'
        else:
            report_callback(f"❌ Ваша ОС ({os_name.capitalize()} {os_version}) не поддерживается.", 1.0)
            return None

    def install(self, host: str, username: str, password: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Полный цикл установки FastPanel с надежной проверкой каждого шага и лога вывода.
        """
        result = {
            'success': False, 'admin_url': None, 'admin_password': None,
            'error': None, 'install_time': None
        }
        installer_path = "/tmp/fastpanel_installer.sh"

        def report(message, progress):
            logger.info(message)
            if callback:
                callback(message, progress)

        report(f"Подключение к {host}...", 0.05)
        if not self.ssh.connect(host, username, password):
            result['error'] = f"Не удалось подключиться к {host}"
            report(result['error'], 1.0)
            return result

        try:
            package_manager = self._check_os(report)
            if not package_manager:
                result['error'] = "Операционная система не поддерживается."
                return result

            report("Шаг 2: Установка необходимых пакетов (curl)...", 0.25)
            prep_command = "apt-get update && apt-get install -y ca-certificates curl" if package_manager == 'apt' else "yum makecache && yum install -y ca-certificates curl"
            
            prep_result = self.ssh.execute(prep_command, get_pty=True)
            if not prep_result.success:
                result['error'] = f"Ошибка при установке зависимостей: {prep_result.stderr}"
                report(result['error'], 1.0)
                return result
            report("✅ Зависимости успешно установлены.", 0.3)

            report("Шаг 3: Загрузка установочного скрипта...", 0.4)
            download_url = "https://repo.fastpanel.direct/install_fastpanel.sh"
            download_cmd = f"curl -sSLf {download_url} -o {installer_path}"
            
            download_result = None
            max_retries = 3
            for attempt in range(max_retries):
                report(f"Попытка загрузки ({attempt + 1}/{max_retries}) с {download_url}...", 0.4 + (attempt * 0.02))
                download_result = self.ssh.execute(download_cmd)
                if download_result.success:
                    break
                report(f"⚠️ Ошибка загрузки (код: {download_result.exit_code}). Повтор через 5 секунд...", 0.4 + (attempt * 0.02))
                if attempt < max_retries - 1:
                    time.sleep(5)
            
            if not download_result or not download_result.success:
                result['error'] = f"Не удалось скачать скрипт установки после {max_retries} попыток. Код ошибки: {download_result.exit_code if download_result else 'N/A'}"
                report(result['error'], 1.0)
                return result
            
            report("✅ Скрипт успешно загружен.", 0.5)
            
            report("Шаг 4: Запуск скрипта установки FastPanel...", 0.6)
            report("Это может занять 5-15 минут...", 0.65)
            
            install_cmd = f"bash {installer_path}"
            admin_password = None
            installation_failed_in_log = False
            
            def progress_handler(line):
                nonlocal admin_password, installation_failed_in_log
                report(line, 0.8)
                
                if "[failed]" in line.lower() or "[ошибка]" in line.lower():
                    installation_failed_in_log = True
                    logger.error(f"Обнаружена ошибка в логе установки: {line}")

                # Улучшенная, нечувствительная к регистру проверка
                if "password:" in line.lower():
                    match = re.search(r'Password:\s*(\S+)', line, re.IGNORECASE)
                    if match:
                        admin_password = match.group(1).strip()
                        logger.info("Пароль администратора найден!")

            exec_result = self.ssh.execute_with_progress(install_cmd, callback=progress_handler)

            self.ssh.execute(f"rm -f {installer_path}")
            report("Очистка временных файлов...", 0.95)

            if exec_result.success and admin_password and not installation_failed_in_log:
                result.update({
                    'success': True,
                    'admin_url': f"https://{host}:8888",
                    'admin_password': admin_password,
                    'install_time': datetime.now().isoformat()
                })
                report("\n✅ Установка успешно завершена!", 1.0)
            else:
                if installation_failed_in_log:
                    result['error'] = "Во время установки произошла ошибка. Проверьте лог на наличие [Failed]."
                elif not admin_password:
                    result['error'] = "Скрипт завершился, но пароль не был найден. Вероятно, установка не удалась."
                else:
                    result['error'] = f"Скрипт установки завершился с ошибкой: {exec_result.stderr}"
                report(f"\n❌ Ошибка установки: {result['error']}", 1.0)

        except Exception as e:
            logger.error(f"Критическая ошибка во время установки: {e}", exc_info=True)
            result['error'] = str(e)
            report(f"\n❌ Критическая ошибка: {e}", 1.0)
        finally:
            self.ssh.disconnect()
            report("SSH соединение закрыто.", 1.0)

        return result

    def create_site(self, domain: str, php_version: str = "7.4") -> Dict[str, Any]:
        fp_path = self._get_fastpanel_path()
        if not fp_path: return {"success": False, "error": "Не удалось найти утилиту fastpanel на сервере."}

        site_user = domain.split('.')[0].replace('-', '_')[:12] + "_usr"
        cmd = f"{fp_path} sites create --server-name='{domain}' --owner='{site_user}' --create-user --php-version='{php_version}'"
        
        logger.info(f"Выполнение команды создания сайта: {cmd}")
        result = self.ssh.execute(cmd)

        if not result.success:
            logger.error(f"Ошибка создания сайта {domain}: {result.stderr}")
            return {"success": False, "error": result.stderr}
        
        expected_path = f"/var/www/{site_user}/data/www/{domain}"
        check_result = self.ssh.execute(f"test -d {expected_path}")
        
        if not check_result.success:
            error_msg = f"Сайт создан, но не найден по ожидаемому пути: {expected_path}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        return {"success": True, "site_user": site_user, "path": expected_path}

    def create_ftp_account(self, domain: str) -> Dict[str, Any]:
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
        domain = domain_info['domain']
        updated_domain_data = domain_info.copy()

        def report_progress(message):
            if progress_callback:
                progress_callback(f"[{domain}] {message}")

        try:
            report_progress("Шаг 1: Создание сайта...")
            site_result = self.create_site(domain)
            if not site_result['success']:
                report_progress(f"ОШИБКА: Не удалось создать сайт. {site_result.get('error', '')}")
                return updated_domain_data
            
            updated_domain_data.update({
                'site_user': site_result['site_user'],
                'path': site_result['path']
            })
            report_progress(f"Сайт успешно создан. Пользователь: {site_result['site_user']}")

            report_progress("Шаг 2: Создание FTP-аккаунта...")
            ftp_result = self.create_ftp_account(domain)
            if ftp_result['success']:
                updated_domain_data.update({
                    'ftp_user': ftp_result['login'],
                    'ftp_password': ftp_result['password']
                })
                report_progress("FTP-аккаунт успешно создан.")
            else:
                report_progress(f"ПРЕДУПРЕЖДЕНИЕ: Не удалось создать FTP-аккаунт. {ftp_result.get('error', '')}")

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
