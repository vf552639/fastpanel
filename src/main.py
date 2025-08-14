#!/usr/bin/env python3
"""
FastPanel Automation MVP
Минимальная версия для быстрого старта
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional
import paramiko
from pathlib import Path

# Конфигурация
DATA_FILE = Path("data/servers.json")
LOG_FILE = Path("logs/automation.log")

@dataclass
class Server:
    """Модель сервера"""
    id: str
    name: str
    ip: str
    ssh_user: str = "root"
    ssh_port: int = 22
    fastpanel_installed: bool = False
    admin_url: Optional[str] = None
    admin_password: Optional[str] = None
    created_at: str = ""
    
class ServerManager:
    """Управление серверами - упрощенная версия"""
    
    def __init__(self):
        self.servers: List[Server] = []
        self.load_servers()
    
    def load_servers(self):
        """Загрузка серверов из JSON"""
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                self.servers = [Server(**s) for s in data]
    
    def save_servers(self):
        """Сохранение серверов в JSON"""
        DATA_FILE.parent.mkdir(exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump([asdict(s) for s in self.servers], f, indent=2)
    
    def add_server(self, server: Server) -> bool:
        """Добавление нового сервера"""
        # Проверка уникальности
        if any(s.ip == server.ip for s in self.servers):
            return False
        self.servers.append(server)
        self.save_servers()
        return True

class FastPanelInstaller:
    """Установщик FastPanel - упрощенная версия"""
    
    @staticmethod
    def install(server: Server, ssh_password: str) -> dict:
        """
        Установка FastPanel на сервер
        Возвращает данные для входа
        """
        result = {
            'success': False,
            'admin_url': None,
            'admin_password': None,
            'error': None
        }
        
        try:
            # SSH подключение
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                server.ip,
                port=server.ssh_port,
                username=server.ssh_user,
                password=ssh_password,
                timeout=30
            )
            
            # Команда установки FastPanel
            install_cmd = "wget -O - http://fastpanel.direct/install_ru.sh | bash -"
            
            print(f"🚀 Начинаем установку FastPanel на {server.ip}...")
            stdin, stdout, stderr = ssh.exec_command(install_cmd, get_pty=True)
            
            # Читаем вывод для получения данных админа
            admin_password = None
            for line in stdout:
                print(f"  {line.strip()}")
                # Парсим пароль админа из вывода
                if "Пароль администратора:" in line or "Admin password:" in line:
                    admin_password = line.split(":")[-1].strip()
            
            # Проверяем успешность
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                result['success'] = True
                result['admin_url'] = f"https://{server.ip}:8888"
                result['admin_password'] = admin_password or "check_install_output"
                
                # Обновляем данные сервера
                server.fastpanel_installed = True
                server.admin_url = result['admin_url']
                server.admin_password = result['admin_password']
            else:
                result['error'] = stderr.read().decode()
            
            ssh.close()
            
        except Exception as e:
            result['error'] = str(e)
        
        return result

class SimpleCLI:
    """Простой текстовый интерфейс для MVP"""
    
    def __init__(self):
        self.manager = ServerManager()
        self.installer = FastPanelInstaller()
    
    def run(self):
        """Главный цикл"""
        while True:
            self.show_menu()
            choice = input("\n👉 Выберите действие: ").strip()
            
            if choice == '1':
                self.add_server()
            elif choice == '2':
                self.install_fastpanel()
            elif choice == '3':
                self.list_servers()
            elif choice == '0':
                print("👋 До свидания!")
                break
            else:
                print("❌ Неверный выбор")
    
    def show_menu(self):
        """Показать меню"""
        print("\n" + "="*50)
        print("🚀 FastPanel Automation MVP")
        print("="*50)
        print("1. Добавить сервер")
        print("2. Установить FastPanel")
        print("3. Список серверов")
        print("0. Выход")
    
    def add_server(self):
        """Добавление сервера"""
        print("\n📝 Добавление нового сервера")
        print("-" * 30)
        
        name = input("Название сервера: ").strip()
        ip = input("IP адрес: ").strip()
        
        # Создаем сервер с уникальным ID
        import uuid
        from datetime import datetime
        
        server = Server(
            id=str(uuid.uuid4())[:8],
            name=name,
            ip=ip,
            created_at=datetime.now().isoformat()
        )
        
        if self.manager.add_server(server):
            print(f"✅ Сервер {name} добавлен!")
        else:
            print(f"❌ Сервер с IP {ip} уже существует!")
    
    def install_fastpanel(self):
        """Установка FastPanel"""
        if not self.manager.servers:
            print("❌ Нет добавленных серверов")
            return
        
        print("\n📋 Выберите сервер для установки:")
        print("-" * 30)
        
        for i, server in enumerate(self.manager.servers, 1):
            status = "✅ Установлен" if server.fastpanel_installed else "⏳ Не установлен"
            print(f"{i}. {server.name} ({server.ip}) - {status}")
        
        try:
            choice = int(input("\nНомер сервера: ")) - 1
            if 0 <= choice < len(self.manager.servers):
                server = self.manager.servers[choice]
                
                if server.fastpanel_installed:
                    print("ℹ️ FastPanel уже установлен на этом сервере")
                    print(f"🔗 Admin URL: {server.admin_url}")
                    print(f"🔑 Admin Password: {server.admin_password}")
                    return
                
                # Запрашиваем SSH пароль
                import getpass
                ssh_password = getpass.getpass(f"SSH пароль для {server.ip}: ")
                
                # Устанавливаем
                result = self.installer.install(server, ssh_password)
                
                if result['success']:
                    print("\n✅ FastPanel успешно установлен!")
                    print(f"🔗 Admin URL: {result['admin_url']}")
                    print(f"🔑 Admin Password: {result['admin_password']}")
                    self.manager.save_servers()
                else:
                    print(f"\n❌ Ошибка установки: {result['error']}")
            else:
                print("❌ Неверный номер")
        except ValueError:
            print("❌ Введите число")
    
    def list_servers(self):
        """Список серверов"""
        if not self.manager.servers:
            print("\n📭 Список серверов пуст")
            return
        
        print("\n📊 Список серверов")
        print("-" * 50)
        
        for server in self.manager.servers:
            print(f"\n🖥️  {server.name}")
            print(f"   IP: {server.ip}")
            print(f"   ID: {server.id}")
            if server.fastpanel_installed:
                print(f"   ✅ FastPanel установлен")
                print(f"   URL: {server.admin_url}")
            else:
                print(f"   ⏳ FastPanel не установлен")

def main():
    """Точка входа"""
    # Создаем необходимые директории
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
    # Запускаем CLI
    cli = SimpleCLI()
    cli.run()

if __name__ == "__main__":
    main()
