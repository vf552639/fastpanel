"""
SSH Manager - управление SSH подключениями
"""
import paramiko
from typing import Optional, Tuple, List
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SSHResult:
    """Результат выполнения SSH команды"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int

class SSHManager:
    """Менеджер SSH подключений"""
    
    def __init__(self):
        self.client: Optional[paramiko.SSHClient] = None
        self.connected = False
        self.current_host = None
    
    def connect(self, host: str, username: str = "root", 
                password: Optional[str] = None, port: int = 22,
                timeout: int = 30) -> bool:
        """
        Подключение к серверу по SSH
        """
        try:
            if self.client:
                self.disconnect()
            
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            logger.info(f"Подключение к {host}:{port} как {username}")
            
            self.client.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False
            )
            
            self.connected = True
            self.current_host = host
            logger.info(f"Успешное подключение к {host}")
            return True
            
        except paramiko.AuthenticationException:
            logger.error(f"Ошибка аутентификации для {host}")
            return False
        except paramiko.SSHException as e:
            logger.error(f"SSH ошибка при подключении к {host}: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при подключении к {host}: {e}")
            return False
    
    def execute(self, command: str, get_pty: bool = False, 
                timeout: Optional[int] = None) -> SSHResult:
        """
        Выполнение команды на удаленном сервере
        """
        if not self.connected or not self.client:
            logger.error("Нет активного SSH подключения")
            return SSHResult(False, "", "Нет активного подключения", -1)
        
        try:
            logger.debug(f"Выполнение команды: {command[:50]}...")
            
            stdin, stdout, stderr = self.client.exec_command(
                command, 
                get_pty=get_pty,
                timeout=timeout
            )
            
            # Читаем вывод
            stdout_text = stdout.read().decode('utf-8', errors='ignore')
            stderr_text = stderr.read().decode('utf-8', errors='ignore')
            exit_code = stdout.channel.recv_exit_status()
            
            success = exit_code == 0
            
            if success:
                logger.debug(f"Команда выполнена успешно")
            else:
                logger.warning(f"Команда завершилась с кодом {exit_code}")
            
            return SSHResult(success, stdout_text, stderr_text, exit_code)
            
        except Exception as e:
            logger.error(f"Ошибка выполнения команды: {e}")
            return SSHResult(False, "", str(e), -1)
    
    def execute_with_progress(self, command: str, 
                            callback=None) -> SSHResult:
        """
        Выполнение команды с отслеживанием прогресса
        """
        if not self.connected or not self.client:
            return SSHResult(False, "", "Нет активного подключения", -1)
        
        try:
            stdin, stdout, stderr = self.client.exec_command(
                command, 
                get_pty=True
            )
            
            output_lines = []
            
            # Читаем построчно для отображения прогресса
            for line in iter(stdout.readline, ''):
                if not line:
                    break
                output_lines.append(line)
                if callback:
                    callback(line.strip())
            
            stderr_text = stderr.read().decode('utf-8', errors='ignore')
            exit_code = stdout.channel.recv_exit_status()
            
            return SSHResult(
                exit_code == 0,
                ''.join(output_lines),
                stderr_text,
                exit_code
            )
            
        except Exception as e:
            logger.error(f"Ошибка выполнения команды с прогрессом: {e}")
            return SSHResult(False, "", str(e), -1)
    
    def test_connection(self) -> bool:
        """
        Проверка активности соединения
        """
        if not self.connected or not self.client:
            return False
        
        try:
            # Простая команда для проверки
            result = self.execute("echo 'test'")
            return result.success
        except:
            return False
    
    def disconnect(self):
        """
        Закрытие SSH соединения
        """
        if self.client:
            try:
                self.client.close()
                logger.info(f"Отключение от {self.current_host}")
            except:
                pass
            finally:
                self.client = None
                self.connected = False
                self.current_host = None
    
    def __enter__(self):
        """Контекстный менеджер - вход"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход"""
        self.disconnect()

# Вспомогательная функция для быстрого выполнения команды
def quick_execute(host: str, command: str, username: str = "root",
                 password: Optional[str] = None, port: int = 22) -> SSHResult:
    """
    Быстрое выполнение одной команды без сохранения соединения
    """
    with SSHManager() as ssh:
        if ssh.connect(host, username, password, port):
            return ssh.execute(command)
        return SSHResult(False, "", "Не удалось подключиться", -1)
