"""
FastPanel Service - все операции с FastPanel
"""
import re
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from src.core.ssh_manager import SSHManager
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

    def _get_os_info(self) -> Optional[Dict[str, str]]:
        """Определяет ОС, ее имя, семейство и версию."""
        if not self.ssh.connected:
            return None
        
        result = self.ssh.execute("cat /etc/os-release")
        if not result.success:
            return None
            
        os_info = dict(line.split('=', 1) for line in result.stdout.split('\n') if '=' in line)
        os_name = os_info.get('NAME', '').strip('"')
        os_id = os_info.get('ID', '').strip('"').lower()
        os_version = os_info.get('VERSION_ID', '').strip('"')

        family = None
        if "ubuntu" in os_id or "debian" in os_id:
            family = "debian"
        elif "centos" in os_id or "almalinux" in os_id or "rocky" in os_id:
            family = "centos"
        
        if family:
            return {"name": os_name, "family": family, "version": os_version}
        
        return None

    def _configure_firewall(self, callback: Optional[Callable] = None):
        """Проверяет и настраивает UFW для доступа к FastPanel."""
        if callback:
            callback("Проверка настроек файрвола (UFW)...", 0.9)

        status_result = self.ssh.execute("sudo ufw status")
        
        # Если UFW неактивен, ничего делать не нужно
        if "Status: inactive" in status_result.stdout:
            if callback:
                callback("Файрвол неактивен, порт 8888 должен быть доступен.", 0.95)
            return

        # Проверяем, открыт ли уже порт 8888
        if "8888/tcp" in status_result.stdout and "ALLOW" in status_result.stdout:
            if callback:
                callback("Порт 8888 уже открыт в файрволе.", 0.95)
            return
        
        # Если порт закрыт, открываем его
        if callback:
            callback("Порт 8888 закрыт. Открываем...", 0.92)
        
        allow_result = self.ssh.execute("sudo ufw allow 8888/tcp")
        if not allow_result.success:
            logger.warning("Не удалось выполнить команду 'ufw allow 8888/tcp'.")
            if callback:
                callback("⚠️ Не удалось добавить правило для порта 8888.", 0.95)
            return # Прерываем, так как reload не имеет смысла

        if callback:
            callback("Правило для порта 8888 добавлено. Обновляем файрвол...", 0.95)
        
        reload_result = self.ssh.execute("sudo ufw reload")
        if reload_result.success:
            if callback:
                callback("✅ Файрвол успешно обновлен.", 0.98)
        else:
            logger.warning("Не удалось выполнить команду 'ufw reload'.")
            if callback:
                callback("⚠️ Не удалось перезагрузить файрвол.", 0.98)

    def install(self, host: str, username: str, password: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Установка FastPanel с предварительной проверкой совместимости ОС и настройкой файрвола.
        """
        result = {'success': False, 'admin_url': None, 'admin_password': "Not found", 'error': None}

        def update_progress(message: str, progress: float):
            if callback:
                callback(message, progress)

        try:
            update_progress(f"Подключение к {host}...", 0.05)
            if not self.ssh.connect(host, username, password):
                result['error'] = "Не удалось подключиться по SSH. Проверьте IP, логин и пароль."
                update_progress(f"❌ Ошибка: {result['error']}", 0)
                return result
            
            update_progress("✅ Авторизация на сервере прошла успешно!", 0.1)
            
            update_progress("Определение операционной системы...", 0.15)
            os_data = self._get_os_info()
            if not os_data:
                result['error'] = "Не удалось определить ОС или ОС не поддерживается."
                update_progress(f"❌ Ошибка: {result['error']}", 0)
                return result
            
            os_name, os_family, os_version = os_data['name'], os_data['family'], os_data['version']
            update_progress(f"ОС определена: {os_name} {os_version}", 0.2)

            supported_versions = ["20.04", "22.04"]
            if os_family == "debian" and not any(v in os_version for v in supported_versions):
                result['error'] = f"Версия {os_name} {os_version} не поддерживается установщиком FastPanel."
                update_progress(f"❌ Ошибка: {result['error']}", 0)
                return result

            prep_commands = {
                "debian": "apt-get update -qq && apt-get install -y ca-certificates wget",
                "centos": "yum makecache -y && yum install -y ca-certificates wget"
            }
            
            update_progress("Подготовка системы и установка пакетов...", 0.3)
            prep_command = prep_commands.get(os_family)
            prep_result = self.ssh.execute(prep_command, timeout=300)
            if not prep_result.success:
                logger.warning(f"Команда подготовки системы завершилась с ошибкой: {prep_result.stderr}")
                update_progress("⚠️ Предупреждение: не удалось выполнить команды подготовки.", 0.4)
            else:
                update_progress("Система подготовлена.", 0.4)

            update_progress("Запуск установщика FASTPANEL (это может занять несколько минут)...", 0.5)
            install_cmd = "wget https://repo.fastpanel.direct/install_fastpanel.sh -O - | bash -"
            
            output_log = []
            admin_url, admin_password = None, None

            def parse_output(line: str):
                nonlocal admin_url, admin_password
                clean_line = line.strip()
                if not clean_line: return
                
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                clean_line = ansi_escape.sub('', clean_line)

                output_log.append(clean_line)
                update_progress(clean_line, 0.5)

                if clean_line.lower().lstrip().startswith("password:") or clean_line.lower().lstrip().startswith("пароль:"):
                    pass_match = re.search(r':\s*(\S+)', clean_line)
                    if pass_match:
                        admin_password = pass_match.group(1).strip()
                        logger.info(f"Найден пароль администратора: {admin_password}")

                if "https://" in clean_line and ":8888" in clean_line:
                    url_match = re.search(r'(https?://\S+:8888)', clean_line)
                    if url_match: admin_url = url_match.group(1)

            install_result = self.ssh.execute_with_progress(install_cmd, parse_output)

            update_progress("Установка завершена. Обработка результатов...", 0.85)
            if not admin_url: admin_url = f"https://{host}:8888"

            success_phrase = "Congratulations! FASTPANEL successfully installed"
            if (install_result.success or any(success_phrase in line for line in output_log)) and admin_password:
                
                # --- НОВЫЙ БЛОК: НАСТРОЙКА ФАЙРВОЛА ---
                if os_family == "debian": # UFW используется в основном на Debian/Ubuntu
                    self._configure_firewall(update_progress)
                # --- КОНЕЦ НОВОГО БЛОКА ---

                result.update({
                    'success': True, 'admin_url': admin_url, 'admin_password': admin_password,
                    'install_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                update_progress("✅ Установка и настройка успешно завершены!", 1.0)
            else:
                error_details = install_result.stderr or "\n".join(output_log[-10:])
                result['error'] = f"Установка завершилась с ошибкой: {error_details}"
                if not admin_password:
                     result['error'] += "\nНе удалось найти пароль администратора в выводе."
                update_progress(f"❌ {result['error']}", 0)

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Критическая ошибка: {e}", exc_info=True)
            update_progress(f"❌ Критическая ошибка: {e}", 0)
        finally:
            self.ssh.disconnect()
            
        return result
