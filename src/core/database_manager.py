"""
Менеджер базы данных SQLite для FastPanel Automation
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.utils.logger import get_logger

logger = get_logger("database_manager")

class DatabaseManager:
    """Класс для управления всеми операциями с базой данных SQLite."""

    def __init__(self, db_path: Path = Path("data/fastpanel.db")):
        """
        Инициализирует менеджер, подключается к БД и создает таблицы.
        Также выполняет однократную миграцию данных из JSON.
        """
        db_path.parent.mkdir(exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Для доступа к столбцам по имени
        self.cursor = self.conn.cursor()
        self._create_tables()

        if not db_path.exists() or db_path.stat().st_size == 0:
            self._migrate_from_json()

    def _create_tables(self):
        """Создает таблицы в БД, если они не существуют."""
        try:
            # Таблица серверов
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ip TEXT NOT NULL UNIQUE,
                ssh_user TEXT NOT NULL,
                password TEXT,
                fastpanel_installed INTEGER NOT NULL DEFAULT 0,
                admin_url TEXT,
                admin_password TEXT,
                created_at TEXT NOT NULL,
                install_date TEXT
            )
            """)

            # Таблица доменов
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_name TEXT NOT NULL UNIQUE,
                server_id TEXT,
                ftp_user TEXT,
                ftp_password TEXT,
                cloudflare_status TEXT,
                cloudflare_ns TEXT,
                FOREIGN KEY (server_id) REFERENCES servers (id) ON DELETE SET NULL
            )
            """)

            # Таблица настроек
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY UNIQUE,
                value TEXT
            )
            """)
            self.conn.commit()
            logger.info("Таблицы успешно созданы или уже существуют.")
        except sqlite3.Error as e:
            logger.error(f"Ошибка при создании таблиц: {e}", exc_info=True)

    def _migrate_from_json(self):
        """
        Выполняет однократную миграцию данных из старых JSON-файлов в SQLite.
        """
        logger.info("Попытка миграции данных из JSON...")
        json_files = {
            "servers": Path("data/servers.json"),
            "domains": Path("data/domains.json"),
            "credentials": Path("data/credentials.json"),
            "settings": Path("data/settings.json"),
        }

        # Миграция серверов
        if json_files["servers"].exists():
            try:
                with open(json_files["servers"], 'r', encoding='utf-8') as f:
                    servers = json.load(f)
                    for server in servers:
                        self.add_server(server)
                json_files["servers"].rename(json_files["servers"].with_suffix(".json.migrated"))
                logger.info(f"Успешно перенесено {len(servers)} серверов из JSON.")
            except Exception as e:
                logger.error(f"Ошибка миграции servers.json: {e}")

        # Миграция доменов
        if json_files["domains"].exists():
            try:
                with open(json_files["domains"], 'r', encoding='utf-8') as f:
                    domains = json.load(f)
                    for domain in domains:
                        self.add_domain(domain)
                json_files["domains"].rename(json_files["domains"].with_suffix(".json.migrated"))
                logger.info(f"Успешно перенесено {len(domains)} доменов из JSON.")
            except Exception as e:
                logger.error(f"Ошибка миграции domains.json: {e}")

        # Миграция credentials.json и settings.json в одну таблицу settings
        if json_files["credentials"].exists():
            try:
                with open(json_files["credentials"], 'r', encoding='utf-8') as f:
                    creds = json.load(f)
                    for key, value in creds.items():
                        self.save_setting(key, value)
                json_files["credentials"].rename(json_files["credentials"].with_suffix(".json.migrated"))
                logger.info("Успешно перенесены credentials.")
            except Exception as e:
                logger.error(f"Ошибка миграции credentials.json: {e}")

        if json_files["settings"].exists():
            try:
                with open(json_files["settings"], 'r', encoding='utf-8') as f:
                    settings_data = json.load(f)
                    for key, value in settings_data.items():
                         # JSON хранится как строка
                        self.save_setting(key, json.dumps(value))
                json_files["settings"].rename(json_files["settings"].with_suffix(".json.migrated"))
                logger.info("Успешно перенесены settings.")
            except Exception as e:
                logger.error(f"Ошибка миграции settings.json: {e}")


    # --- Методы для работы с серверами ---

    def get_all_servers(self) -> List[Dict[str, Any]]:
        """Возвращает список всех серверов."""
        self.cursor.execute("SELECT * FROM servers ORDER BY created_at DESC")
        return [dict(row) for row in self.cursor.fetchall()]

    def add_server(self, server_data: Dict[str, Any]) -> bool:
        """Добавляет новый сервер в БД."""
        try:
            self.cursor.execute("""
                INSERT INTO servers (id, name, ip, ssh_user, password, fastpanel_installed, admin_url, admin_password, created_at)
                VALUES (:id, :name, :ip, :ssh_user, :password, :fastpanel_installed, :admin_url, :admin_password, :created_at)
            """, {
                'id': server_data.get('id'),
                'name': server_data.get('name'),
                'ip': server_data.get('ip'),
                'ssh_user': server_data.get('ssh_user', 'root'),
                'password': server_data.get('password'),
                'fastpanel_installed': 1 if server_data.get('fastpanel_installed') else 0,
                'admin_url': server_data.get('admin_url'),
                'admin_password': server_data.get('admin_password'),
                'created_at': server_data.get('created_at')
            })
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Сервер с IP {server_data.get('ip')} уже существует.")
            return False
        except Exception as e:
            logger.error(f"Ошибка добавления сервера: {e}", exc_info=True)
            return False


    def update_server(self, server_id: str, server_data: Dict[str, Any]):
        """Обновляет данные сервера."""
        # Преобразуем bool в int для fastpanel_installed, если оно есть
        if 'fastpanel_installed' in server_data:
            server_data['fastpanel_installed'] = 1 if server_data['fastpanel_installed'] else 0
            
        fields = ", ".join([f"{key} = :{key}" for key in server_data.keys()])
        query = f"UPDATE servers SET {fields} WHERE id = :id"
        
        params = server_data.copy()
        params['id'] = server_id
        
        self.cursor.execute(query, params)
        self.conn.commit()


    def delete_server(self, server_id: str):
        """Удаляет сервер по ID."""
        self.cursor.execute("DELETE FROM servers WHERE id = ?", (server_id,))
        self.conn.commit()


    # --- Методы для работы с доменами ---

    def get_all_domains(self) -> List[Dict[str, Any]]:
        """Возвращает список всех доменов."""
        self.cursor.execute("SELECT * FROM domains")
        return [dict(row) for row in self.cursor.fetchall()]

    def add_domain(self, domain_data: Dict[str, Any]) -> bool:
        """Добавляет новый домен."""
        try:
            self.cursor.execute("""
                INSERT INTO domains (domain_name, server_id, ftp_user, ftp_password, cloudflare_status, cloudflare_ns)
                VALUES (:domain_name, :server_id, :ftp_user, :ftp_password, :cloudflare_status, :cloudflare_ns)
            """, {
                'domain_name': domain_data.get('domain'),
                'server_ip': domain_data.get('server_ip'),
                'ftp_user': domain_data.get('ftp_user'),
                'ftp_password': domain_data.get('ftp_password'),
                'cloudflare_status': domain_data.get('cloudflare_status'),
                'cloudflare_ns': ",".join(domain_data.get('cloudflare_ns', []))
            })
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Домен {domain_data.get('domain')} уже существует.")
            return False

    def update_domain(self, domain_name: str, domain_data: Dict[str, Any]):
        """Обновляет данные домена."""
        if 'cloudflare_ns' in domain_data and isinstance(domain_data['cloudflare_ns'], list):
            domain_data['cloudflare_ns'] = ",".join(domain_data['cloudflare_ns'])

        fields = ", ".join([f"{key} = :{key}" for key in domain_data.keys()])
        query = f"UPDATE domains SET {fields} WHERE domain_name = :domain_name"

        params = domain_data.copy()
        params['domain_name'] = domain_name
        
        self.cursor.execute(query, params)
        self.conn.commit()
    
    def delete_domain(self, domain_name: str):
        """Удаляет домен по имени."""
        self.cursor.execute("DELETE FROM domains WHERE domain_name = ?", (domain_name,))
        self.conn.commit()

    # --- Методы для работы с настройками ---

    def get_setting(self, key: str, default: Any = None) -> Optional[str]:
        """Получает значение настройки по ключу."""
        self.cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = self.cursor.fetchone()
        return row['value'] if row else default
        
    def get_all_settings(self) -> Dict[str, Any]:
        """Возвращает все настройки в виде словаря."""
        self.cursor.execute("SELECT key, value FROM settings")
        settings = {}
        for row in self.cursor.fetchall():
            # Пытаемся распарсить JSON, если не получается - возвращаем как строку
            try:
                settings[row['key']] = json.loads(row['value'])
            except (json.JSONDecodeError, TypeError):
                settings[row['key']] = row['value']
        return settings

    def save_setting(self, key: str, value: Any):
        """Сохраняет или обновляет значение настройки."""
        # Если значение - словарь или список, сохраняем как JSON строку
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
            
        self.cursor.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        self.conn.commit()

    def close(self):
        """Закрывает соединение с БД."""
        if self.conn:
            self.conn.close()
