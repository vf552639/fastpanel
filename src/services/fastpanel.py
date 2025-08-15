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

    def _get_os_type(self) -> Optional[str]:
        """Определяет тип ОС на сервере."""
        if not self.ssh.connected:
            return None
        
        result = self.ssh.execute("cat /etc/os-release")
        if not result.success:
            return None
            
        os_info = dict(line.split('=', 1) for line in result.stdout.split('\n') if '=' in line)
        os_name = os_info.get('NAME', '').strip('"').lower()

        if "ubuntu" in os_name or "debian" in os_name:
            return "debian"
        if "centos" in os_name or "almalinux" in os_name or "rocky" in os_name:
            return "centos"
            
        return None

    def install(self, host: str, username: str, password: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Установка FastPanel на сервер с детальным логгированием и определением ОС.
        """
        result = {'success': False, 'admin_url': None, 'admin_password': "Not found", 'error': None}

        def update_progress(message: str, progress: float):
            if callback:
                # Эта функция теперь безопасна и вызывает только callback
                callback(message, progress)

        try:
            update_progress("Подключение...", 0.1)
            if not self.ssh.connect(host, username, password):
                result['error'] = "Не удалось подключиться по SSH"
                update_progress(f"❌ Ошибка: {result['error']}", 0)
                return result
            
            update_progress("Определение ОС...", 0.2)
            os_type = self._get_os_type()
            if not os_type:
                result['error'] = "Не удалось определить ОС"
                update_progress(f"❌ Ошибка: {result['error']}", 0)
                return result
            update_progress(f"ОС определена: {os_type.capitalize()}", 0.3)

            prep_commands = {
                "debian": "apt-get update -qq && apt-get install -y ca-certificates wget",
                "centos": "yum makecache && yum install -y ca-certificates wget"
            }
            
            update_progress("Установка системных пакетов...", 0.4)
            prep_command = prep_commands.get(os_type)
            prep_result = self.ssh.execute(prep_command, timeout=300)
            if not prep_result.success:
                # Это некритичная ошибка, просто логируем
                logger.warning(f"Не удалось выполнить команду подготовки: {prep_result.stderr}")
            
            update_progress("Запуск установщика FASTPANEL...", 0.6)
            install_cmd = "wget https://repo.fastpanel.direct/install_fastpanel.sh -O - | bash -"
            
            output_log = []
            admin_url, admin_password = None, None

            def parse_output(line: str):
                nonlocal admin_url, admin_password
                output_log.append(line)
                update_progress(line, 0.6) # Держим прогресс на 60% во время установки
                
                # Поиск URL
                if "https://" in line and ":8888" in line:
                    url_match = re.search(r'(https?://\S+:8888)', line)
                    if url_match:
                        admin_url = url_match.group(1)
                elif "ttp://" in line and ":8888" in line: # Исправление опечатки
                    url_match = re.search(r'(ttps?://\S+:8888)', line.replace("ttp", "http"))
                    if url_match:
                        # Корректируем URL, подставляя IP сервера
                        admin_url = url_match.group(1).replace(f"//{host}", f"//{host}")
                
                # Поиск пароля
                pass_match = re.search(r'(?:admin password|пароль администратора):\s*(\S+)', line, re.IGNORECASE)
                if pass_match:
                    admin_password = pass_match.group(1)

            install_result = self.ssh.execute_with_progress(install_cmd, parse_output)

            update_progress("Получение данных доступа...", 0.9)
            if not admin_url: # Если URL не был найден в логе
                admin_url = f"https://{host}:8888"

            if install_result.success:
                result.update({
                    'success': True,
                    'admin_url': admin_url,
                    'admin_password': admin_password,
                    'install_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                update_progress("✅ Установка успешно завершена!", 1.0)
            else:
                result['error'] = f"Установка завершилась с ошибкой: \n{''.join(install_result.stderr or output_log)}"
                update_progress(f"❌ {result['error']}", 0)

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Критическая ошибка при установке: {e}", exc_info=True)
            update_progress(f"❌ Критическая ошибка: {e}", 0)
        finally:
            self.ssh.disconnect()
            
        return result
