"""
FastPanel Automation GUI
Современный интерфейс для управления серверами и FastPanel
"""

import customtkinter as ctk
from typing import Optional, Dict, List
import json
from pathlib import Path
from datetime import datetime
import threading
from PIL import Image
import os

# Настройка внешнего вида
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ServerCard(ctk.CTkFrame):
    """Карточка сервера для отображения в списке"""
    
    def __init__(self, parent, server_data: dict, on_click=None, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.server_data = server_data
        self.on_click = on_click
        
        # Настройка внешнего вида карточки
        self.configure(
            corner_radius=10,
            fg_color=("#ffffff", "#2b2b2b"),
            border_width=1,
            border_color=("#e0e0e0", "#404040")
        )
        
        self._create_widgets()
    
    def _create_widgets(self):
        # Основной контейнер
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=15, pady=12)
        
        # Верхняя часть - название и статус
        top_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_frame.pack(fill="x", pady=(0, 8))
        
        # Иконка сервера
        server_icon = ctk.CTkLabel(
            top_frame,
            text="🖥️",
            font=ctk.CTkFont(size=24)
        )
        server_icon.pack(side="left", padx=(0, 10))
        
        # Информация о сервере
        info_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)
        
        # Название сервера
        name_label = ctk.CTkLabel(
            info_frame,
            text=self.server_data.get("name", "Безымянный сервер"),
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        name_label.pack(fill="x")
        
        # IP адрес
        ip_label = ctk.CTkLabel(
            info_frame,
            text=f"IP: {self.server_data.get('ip', 'Не указан')}",
            font=ctk.CTkFont(size=12),
            text_color=("#666666", "#aaaaaa"),
            anchor="w"
        )
        ip_label.pack(fill="x")
        
        # Статус FastPanel
        status_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        status_frame.pack(side="right")
        
        if self.server_data.get("fastpanel_installed"):
            status_badge = ctk.CTkLabel(
                status_frame,
                text="✅ FastPanel установлен",
                font=ctk.CTkFont(size=11),
                fg_color=("#4caf50", "#2e7d32"),
                corner_radius=5,
                text_color="white"
            )
            status_badge.pack(padx=8, pady=4)
        else:
            status_badge = ctk.CTkLabel(
                status_frame,
                text="⏳ Не установлен",
                font=ctk.CTkFont(size=11),
                fg_color=("#ff9800", "#f57c00"),
                corner_radius=5,
                text_color="white"
            )
            status_badge.pack(padx=8, pady=4)
        
        # Разделитель
        separator = ctk.CTkFrame(main_frame, height=1, fg_color=("#e0e0e0", "#404040"))
        separator.pack(fill="x", pady=8)
        
        # Нижняя часть - действия
        bottom_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        bottom_frame.pack(fill="x")
        
        # Кнопки действий
        if self.server_data.get("fastpanel_installed"):
            # Кнопка управления
            manage_btn = ctk.CTkButton(
                bottom_frame,
                text="Управление",
                width=100,
                height=28,
                font=ctk.CTkFont(size=12),
                command=lambda: self._on_manage()
            )
            manage_btn.pack(side="left", padx=(0, 5))
            
            # Кнопка панели
            panel_btn = ctk.CTkButton(
                bottom_frame,
                text="Открыть панель",
                width=100,
                height=28,
                font=ctk.CTkFont(size=12),
                fg_color=("#4caf50", "#2e7d32"),
                hover_color=("#45a049", "#1b5e20"),
                command=lambda: self._open_panel()
            )
            panel_btn.pack(side="left", padx=5)
        else:
            # Кнопка установки
            install_btn = ctk.CTkButton(
                bottom_frame,
                text="Установить FastPanel",
                width=150,
                height=28,
                font=ctk.CTkFont(size=12),
                fg_color=("#2196f3", "#1976d2"),
                hover_color=("#1976d2", "#1565c0"),
                command=lambda: self._on_install()
            )
            install_btn.pack(side="left")
        
        # Кнопка удаления
        delete_btn = ctk.CTkButton(
            bottom_frame,
            text="🗑️",
            width=30,
            height=28,
            fg_color=("#f44336", "#d32f2f"),
            hover_color=("#da190b", "#b71c1c"),
            command=lambda: self._on_delete()
        )
        delete_btn.pack(side="right")
        
        # Добавляем дату создания
        if self.server_data.get("created_at"):
            date_label = ctk.CTkLabel(
                bottom_frame,
                text=f"Добавлен: {self.server_data['created_at'][:10]}",
                font=ctk.CTkFont(size=10),
                text_color=("#999999", "#666666")
            )
            date_label.pack(side="right", padx=(0, 10))
    
    def _on_manage(self):
        if self.on_click:
            self.on_click("manage", self.server_data)
    
    def _on_install(self):
        if self.on_click:
            self.on_click("install", self.server_data)
    
    def _open_panel(self):
        if self.on_click:
            self.on_click("open_panel", self.server_data)
    
    def _on_delete(self):
        if self.on_click:
            self.on_click("delete", self.server_data)


class FastPanelApp(ctk.CTk):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        
        # Настройка окна
        self.title("FastPanel Automation")
        self.geometry("1200x700")
        self.minsize(1000, 600)
        
        # Центрирование окна
        self.center_window()
        
        # Инициализация данных
        self.servers = []
        self.current_tab = "servers"
        
        # Создание интерфейса
        self._create_widgets()
        
        # Загрузка данных
        self.load_servers()
    
    def center_window(self):
        """Центрирование окна на экране"""
        self.update_idletasks()
        width = 1200
        height = 700
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def _create_widgets(self):
        """Создание всех виджетов интерфейса"""
        
        # Главный контейнер
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Боковая панель
        self._create_sidebar(main_container)
        
        # Область контента
        self.content_frame = ctk.CTkFrame(
            main_container,
            fg_color=("#f5f5f5", "#1a1a1a"),
            corner_radius=0
        )
        self.content_frame.pack(side="right", fill="both", expand=True)
        
        # Заголовок
        self._create_header()
        
        # Область для вкладок
        self.tab_container = ctk.CTkFrame(
            self.content_frame,
            fg_color="transparent"
        )
        self.tab_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Показываем вкладку серверов по умолчанию
        self.show_servers_tab()
    
    def _create_sidebar(self, parent):
        """Создание боковой панели навигации"""
        self.sidebar = ctk.CTkFrame(
            parent,
            width=250,
            fg_color=("#ffffff", "#2b2b2b"),
            corner_radius=0
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Логотип/Заголовок
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=20)
        
        app_title = ctk.CTkLabel(
            logo_frame,
            text="🚀 FastPanel",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        app_title.pack()
        
        app_subtitle = ctk.CTkLabel(
            logo_frame,
            text="Automation Tool",
            font=ctk.CTkFont(size=12),
            text_color=("#666666", "#aaaaaa")
        )
        app_subtitle.pack()
        
        # Разделитель
        ctk.CTkFrame(
            self.sidebar,
            height=2,
            fg_color=("#e0e0e0", "#404040")
        ).pack(fill="x", padx=20, pady=10)
        
        # Кнопки навигации
        nav_buttons = [
            ("🖥️", "Серверы", self.show_servers_tab),
            ("➕", "Добавить сервер", self.show_add_server_tab),
            ("☁️", "Cloudflare", self.show_cloudflare_tab),
            ("🔧", "Настройки", self.show_settings_tab),
            ("📊", "Мониторинг", self.show_monitoring_tab),
            ("📝", "Логи", self.show_logs_tab)
        ]
        
        for icon, text, command in nav_buttons:
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"{icon}  {text}",
                font=ctk.CTkFont(size=14),
                height=40,
                fg_color="transparent",
                text_color=("#000000", "#ffffff"),
                hover_color=("#e0e0e0", "#404040"),
                anchor="w",
                command=command
            )
            btn.pack(fill="x", padx=15, pady=2)
        
        # Информация внизу
        info_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        info_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        
        version_label = ctk.CTkLabel(
            info_frame,
            text="Version 0.1.0 MVP",
            font=ctk.CTkFont(size=10),
            text_color=("#999999", "#666666")
        )
        version_label.pack()
        
        # Статус подключения
        self.status_label = ctk.CTkLabel(
            info_frame,
            text="● Готов к работе",
            font=ctk.CTkFont(size=11),
            text_color=("#4caf50", "#4caf50")
        )
        self.status_label.pack(pady=(5, 0))
    
    def _create_header(self):
        """Создание заголовка области контента"""
        header_frame = ctk.CTkFrame(
            self.content_frame,
            height=80,
            fg_color="transparent"
        )
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        header_frame.pack_propagate(False)
        
        # Заголовок страницы
        self.page_title = ctk.CTkLabel(
            header_frame,
            text="Управление серверами",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        self.page_title.pack(side="left")
        
        # Кнопка обновления
        refresh_btn = ctk.CTkButton(
            header_frame,
            text="🔄 Обновить",
            width=100,
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color=("#2196f3", "#1976d2"),
            hover_color=("#1976d2", "#1565c0"),
            command=self.refresh_data
        )
        refresh_btn.pack(side="right", padx=(10, 0))
        
        # Поиск
        self.search_entry = ctk.CTkEntry(
            header_frame,
            placeholder_text="🔍 Поиск серверов...",
            width=250,
            height=32,
            font=ctk.CTkFont(size=12)
        )
        self.search_entry.pack(side="right", padx=10)
    
    def show_servers_tab(self):
        """Отображение вкладки со списком серверов"""
        self.clear_tab_container()
        self.page_title.configure(text="Управление серверами")
        self.current_tab = "servers"
        
        # Скроллируемая область для списка серверов
        scrollable = ctk.CTkScrollableFrame(
            self.tab_container,
            fg_color="transparent"
        )
        scrollable.pack(fill="both", expand=True)
        
        if not self.servers:
            # Пустое состояние
            empty_frame = ctk.CTkFrame(scrollable, fg_color="transparent")
            empty_frame.pack(expand=True, pady=50)
            
            ctk.CTkLabel(
                empty_frame,
                text="📭",
                font=ctk.CTkFont(size=64)
            ).pack()
            
            ctk.CTkLabel(
                empty_frame,
                text="Нет добавленных серверов",
                font=ctk.CTkFont(size=18, weight="bold")
            ).pack(pady=(20, 10))
            
            ctk.CTkLabel(
                empty_frame,
                text="Добавьте первый сервер, чтобы начать работу",
                font=ctk.CTkFont(size=14),
                text_color=("#666666", "#aaaaaa")
            ).pack()
            
            ctk.CTkButton(
                empty_frame,
                text="➕ Добавить сервер",
                font=ctk.CTkFont(size=14),
                width=200,
                height=40,
                command=self.show_add_server_tab
            ).pack(pady=20)
        else:
            # Отображаем карточки серверов
            for server in self.servers:
                card = ServerCard(
                    scrollable,
                    server,
                    on_click=self.handle_server_action
                )
                card.pack(fill="x", pady=5)
    
    def show_add_server_tab(self):
        """Отображение вкладки добавления сервера"""
        self.clear_tab_container()
        self.page_title.configure(text="Добавление нового сервера")
        self.current_tab = "add_server"
        
        # Форма добавления
        form_frame = ctk.CTkFrame(
            self.tab_container,
            fg_color=("#ffffff", "#2b2b2b"),
            corner_radius=10
        )
        form_frame.pack(fill="both", padx=100, pady=50)
        
        # Заголовок формы
        ctk.CTkLabel(
            form_frame,
            text="Параметры сервера",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(30, 20))
        
        # Поля формы
        fields_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        fields_frame.pack(padx=50, pady=20)
        
        # Название сервера
        ctk.CTkLabel(
            fields_frame,
            text="Название сервера",
            font=ctk.CTkFont(size=12),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        self.server_name_entry = ctk.CTkEntry(
            fields_frame,
            placeholder_text="Например: Production Server",
            width=400,
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.server_name_entry.pack(pady=(0, 15))
        
        # IP адрес
        ctk.CTkLabel(
            fields_frame,
            text="IP адрес",
            font=ctk.CTkFont(size=12),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        self.server_ip_entry = ctk.CTkEntry(
            fields_frame,
            placeholder_text="192.168.1.100",
            width=400,
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.server_ip_entry.pack(pady=(0, 15))
        
        # SSH порт
        ctk.CTkLabel(
            fields_frame,
            text="SSH порт",
            font=ctk.CTkFont(size=12),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        self.server_port_entry = ctk.CTkEntry(
            fields_frame,
            placeholder_text="22",
            width=400,
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.server_port_entry.pack(pady=(0, 15))
        self.server_port_entry.insert(0, "22")
        
        # SSH пользователь
        ctk.CTkLabel(
            fields_frame,
            text="SSH пользователь",
            font=ctk.CTkFont(size=12),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        self.server_user_entry = ctk.CTkEntry(
            fields_frame,
            placeholder_text="root",
            width=400,
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.server_user_entry.pack(pady=(0, 15))
        self.server_user_entry.insert(0, "root")
        
        # Кнопки
        buttons_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        buttons_frame.pack(pady=(10, 30))
        
        ctk.CTkButton(
            buttons_frame,
            text="Отмена",
            width=120,
            height=40,
            fg_color="transparent",
            border_width=1,
            text_color=("#000000", "#ffffff"),
            border_color=("#e0e0e0", "#404040"),
            hover_color=("#f0f0f0", "#333333"),
            command=self.show_servers_tab
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="Добавить сервер",
            width=150,
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.add_server
        ).pack(side="left", padx=5)
    
    def show_cloudflare_tab(self):
        """Отображение вкладки Cloudflare"""
        self.clear_tab_container()
        self.page_title.configure(text="Интеграция с Cloudflare")
        self.current_tab = "cloudflare"
        
        # Контейнер для Cloudflare
        cf_frame = ctk.CTkFrame(
            self.tab_container,
            fg_color=("#ffffff", "#2b2b2b"),
            corner_radius=10
        )
        cf_frame.pack(fill="both", expand=True, padx=50, pady=30)
        
        # Заголовок
        ctk.CTkLabel(
            cf_frame,
            text="☁️",
            font=ctk.CTkFont(size=64)
        ).pack(pady=(40, 20))
        
        ctk.CTkLabel(
            cf_frame,
            text="Cloudflare DNS Management",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack()
        
        ctk.CTkLabel(
            cf_frame,
            text="Управление DNS записями и настройками Cloudflare",
            font=ctk.CTkFont(size=14),
            text_color=("#666666", "#aaaaaa")
        ).pack(pady=(10, 30))
        
        # API настройки
        api_frame = ctk.CTkFrame(cf_frame, fg_color="transparent")
        api_frame.pack(padx=100, pady=20)
        
        ctk.CTkLabel(
            api_frame,
            text="API Token",
            font=ctk.CTkFont(size=12),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        api_entry = ctk.CTkEntry(
            api_frame,
            placeholder_text="Введите ваш Cloudflare API Token",
            width=400,
            height=40,
            show="*"
        )
        api_entry.pack(pady=(0, 15))
        
        ctk.CTkButton(
            api_frame,
            text="Подключить Cloudflare",
            width=200,
            height=40,
            fg_color=("#ff9800", "#f57c00"),
            hover_color=("#f57c00", "#e65100")
        ).pack()
        
        # Информация
        info_label = ctk.CTkLabel(
            cf_frame,
            text="⚠️ Функционал Cloudflare будет доступен в следующей версии",
            font=ctk.CTkFont(size=12),
            text_color=("#ff9800", "#ffa726")
        )
        info_label.pack(pady=(30, 20))
    
    def show_settings_tab(self):
        """Отображение вкладки настроек"""
        self.clear_tab_container()
        self.page_title.configure(text="Настройки приложения")
        self.current_tab = "settings"
        
        # Скроллируемая область
        scrollable = ctk.CTkScrollableFrame(
            self.tab_container,
            fg_color="transparent"
        )
        scrollable.pack(fill="both", expand=True)
        
        # Секция SSH
        ssh_section = self._create_settings_section(
            scrollable,
            "SSH Настройки",
            "Параметры подключения по умолчанию"
        )
        
        ssh_timeout = ctk.CTkEntry(ssh_section, placeholder_text="30 секунд")
        self._add_setting_field(ssh_section, "Таймаут подключения", ssh_timeout)
        
        ssh_port = ctk.CTkEntry(ssh_section, placeholder_text="22")
        self._add_setting_field(ssh_section, "Порт по умолчанию", ssh_port)
        
        # Секция FastPanel
        fp_section = self._create_settings_section(
            scrollable,
            "FastPanel",
            "Настройки установки и управления"
        )
        
        fp_url = ctk.CTkEntry(fp_section, placeholder_text="http://fastpanel.direct/install_ru.sh")
        self._add_setting_field(fp_section, "URL установщика", fp_url)
        
        fp_port = ctk.CTkEntry(fp_section, placeholder_text="8888")
        self._add_setting_field(fp_section, "Порт админ-панели", fp_port)
        
        # Секция Безопасность
        security_section = self._create_settings_section(
            scrollable,
            "Безопасность",
            "Шифрование и защита данных"
        )
        
        encryption_switch = ctk.CTkSwitch(
            security_section,
            text="Шифровать сохраненные пароли",
            font=ctk.CTkFont(size=12)
        )
        encryption_switch.pack(pady=10, padx=20, anchor="w")
        
        # Секция Внешний вид
        appearance_section = self._create_settings_section(
            scrollable,
            "Внешний вид",
            "Тема и оформление"
        )
        
        theme_frame = ctk.CTkFrame(appearance_section, fg_color="transparent")
        theme_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            theme_frame,
            text="Тема приложения",
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(0, 20))
        
        theme_menu = ctk.CTkOptionMenu(
            theme_frame,
            values=["Темная", "Светлая", "Системная"],
            width=150
        )
        theme_menu.pack(side="left")
        
        # Кнопка сохранения
        save_btn = ctk.CTkButton(
            scrollable,
            text="Сохранить настройки",
            width=200,
            height=40,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        save_btn.pack(pady=30)
    
    def show_monitoring_tab(self):
        """Отображение вкладки мониторинга"""
        self.clear_tab_container()
        self.page_title.configure(text="Мониторинг серверов")
        self.current_tab = "monitoring"
        
        # Контейнер мониторинга
        monitor_frame = ctk.CTkFrame(
            self.tab_container,
            fg_color="transparent"
        )
        monitor_frame.pack(fill="both", expand=True)
        
        # Статистика
        stats_frame = ctk.CTkFrame(
            monitor_frame,
            fg_color=("#ffffff", "#2b2b2b"),
            corner_radius=10
        )
        stats_frame.pack(fill="x", pady=(0, 20))
        
        stats_container = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_container.pack(padx=30, pady=20)
        
        # Карточки статистики
        stats = [
            ("Всего серверов", len(self.servers), "#2196f3"),
            ("С FastPanel", sum(1 for s in self.servers if s.get("fastpanel_installed")), "#4caf50"),
            ("Активные", "N/A", "#ff9800"),
            ("Требуют внимания", "0", "#f44336")
        ]
        
        for title, value, color in stats:
            stat_card = ctk.CTkFrame(
                stats_container,
                width=200,
                height=100,
                fg_color=("#f5f5f5", "#1a1a1a"),
                corner_radius=8
            )
            stat_card.pack(side="left", padx=10)
            stat_card.pack_propagate(False)
            
            card_content = ctk.CTkFrame(stat_card, fg_color="transparent")
            card_content.pack(expand=True)
            
            ctk.CTkLabel(
                card_content,
                text=str(value),
                font=ctk.CTkFont(size=32, weight="bold"),
                text_color=color
            ).pack()
            
            ctk.CTkLabel(
                card_content,
                text=title,
                font=ctk.CTkFont(size=12),
                text_color=("#666666", "#aaaaaa")
            ).pack()
        
        # Плейсхолдер для графиков
        chart_frame = ctk.CTkFrame(
            monitor_frame,
            fg_color=("#ffffff", "#2b2b2b"),
            corner_radius=10,
            height=300
        )
        chart_frame.pack(fill="both", expand=True)
        chart_frame.pack_propagate(False)
        
        ctk.CTkLabel(
            chart_frame,
            text="📊 Графики мониторинга будут доступны в следующей версии",
            font=ctk.CTkFont(size=16),
            text_color=("#666666", "#aaaaaa")
        ).pack(expand=True)
    
    def show_logs_tab(self):
        """Отображение вкладки логов"""
        self.clear_tab_container()
        self.page_title.configure(text="Журнал событий")
        self.current_tab = "logs"
        
        # Контейнер для логов
        logs_frame = ctk.CTkFrame(
            self.tab_container,
            fg_color=("#ffffff", "#2b2b2b"),
            corner_radius=10
        )
        logs_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Панель фильтров
        filter_frame = ctk.CTkFrame(logs_frame, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            filter_frame,
            text="Фильтры:",
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(0, 10))
        
        # Фильтр по уровню
        level_menu = ctk.CTkOptionMenu(
            filter_frame,
            values=["Все", "Info", "Warning", "Error"],
            width=100
        )
        level_menu.pack(side="left", padx=5)
        
        # Фильтр по дате
        date_menu = ctk.CTkOptionMenu(
            filter_frame,
            values=["Сегодня", "Последние 7 дней", "Последние 30 дней", "Все"],
            width=150
        )
        date_menu.pack(side="left", padx=5)
        
        # Кнопка очистки
        ctk.CTkButton(
            filter_frame,
            text="Очистить логи",
            width=100,
            height=28,
            fg_color=("#f44336", "#d32f2f"),
            hover_color=("#da190b", "#b71c1c")
        ).pack(side="right")
        
        # Область логов
        logs_text = ctk.CTkTextbox(
            logs_frame,
            font=ctk.CTkFont(family="Courier", size=11),
            fg_color=("#1e1e1e", "#0a0a0a"),
            text_color=("#00ff00", "#00ff00"),
            corner_radius=5
        )
        logs_text.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        
        # Пример логов
        sample_logs = """[2024-01-15 10:23:45] INFO: Приложение запущено
[2024-01-15 10:23:46] INFO: Загружен список серверов (3 шт.)
[2024-01-15 10:24:12] INFO: Подключение к серверу 192.168.1.100
[2024-01-15 10:24:13] SUCCESS: Успешное подключение по SSH
[2024-01-15 10:24:15] INFO: Начата установка FastPanel
[2024-01-15 10:28:43] SUCCESS: FastPanel успешно установлен
[2024-01-15 10:28:44] INFO: Пароль администратора сохранен
[2024-01-15 10:30:21] WARNING: Не удалось подключиться к серверу 192.168.1.101
[2024-01-15 10:30:22] ERROR: SSH timeout после 30 секунд
[2024-01-15 10:31:05] INFO: Повторная попытка подключения...
[2024-01-15 10:31:36] SUCCESS: Подключение восстановлено
[2024-01-15 10:32:11] INFO: Создан новый сайт: example.com
[2024-01-15 10:32:12] INFO: DNS записи добавлены в Cloudflare
"""
        logs_text.insert("1.0", sample_logs)
        logs_text.configure(state="disabled")
    
    def _create_settings_section(self, parent, title, description):
        """Создание секции настроек"""
        section = ctk.CTkFrame(
            parent,
            fg_color=("#ffffff", "#2b2b2b"),
            corner_radius=10
        )
        section.pack(fill="x", pady=10)
        
        # Заголовок секции
        header_frame = ctk.CTkFrame(section, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header_frame,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            header_frame,
            text=description,
            font=ctk.CTkFont(size=11),
            text_color=("#666666", "#aaaaaa")
        ).pack(anchor="w", pady=(2, 0))
        
        return section
    
    def _add_setting_field(self, parent, label, widget):
        """Добавление поля настройки"""
        field_frame = ctk.CTkFrame(parent, fg_color="transparent")
        field_frame.pack(fill="x", padx=20, pady=8)
        
        ctk.CTkLabel(
            field_frame,
            text=label,
            font=ctk.CTkFont(size=12),
            width=150,
            anchor="w"
        ).pack(side="left")
        
        widget.configure(width=250)
        widget.pack(side="left", padx=(20, 0))
    
    def clear_tab_container(self):
        """Очистка контейнера вкладок"""
        for widget in self.tab_container.winfo_children():
            widget.destroy()
    
    def handle_server_action(self, action, server_data):
        """Обработка действий с сервером"""
        if action == "manage":
            self.show_server_management(server_data)
        elif action == "install":
            self.show_install_dialog(server_data)
        elif action == "open_panel":
            import webbrowser
            if server_data.get("admin_url"):
                webbrowser.open(server_data["admin_url"])
        elif action == "delete":
            self.confirm_delete_server(server_data)
    
    def show_server_management(self, server_data):
        """Показать окно управления сервером"""
        # Создаем новое окно
        manage_window = ctk.CTkToplevel(self)
        manage_window.title(f"Управление: {server_data['name']}")
        manage_window.geometry("800x600")
        
        # Центрируем окно
        manage_window.update_idletasks()
        x = (manage_window.winfo_screenwidth() // 2) - 400
        y = (manage_window.winfo_screenheight() // 2) - 300
        manage_window.geometry(f"800x600+{x}+{y}")
        
        # Заголовок
        header = ctk.CTkFrame(manage_window, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(
            header,
            text=f"🖥️ {server_data['name']}",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            header,
            text=f"IP: {server_data['ip']} | Статус: {'✅ FastPanel установлен' if server_data.get('fastpanel_installed') else '⏳ Не установлен'}",
            font=ctk.CTkFont(size=12),
            text_color=("#666666", "#aaaaaa")
        ).pack(anchor="w", pady=(5, 0))
        
        # Табы управления
        tabview = ctk.CTkTabview(manage_window)
        tabview.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Вкладка "Информация"
        info_tab = tabview.add("Информация")
        self._create_server_info_tab(info_tab, server_data)
        
        # Вкладка "Сайты"
        sites_tab = tabview.add("Сайты")
        self._create_sites_tab(sites_tab, server_data)
        
        # Вкладка "Базы данных"
        db_tab = tabview.add("Базы данных")
        self._create_databases_tab(db_tab, server_data)
        
        # Вкладка "SSH Терминал"
        terminal_tab = tabview.add("SSH Терминал")
        self._create_terminal_tab(terminal_tab, server_data)
    
    def _create_server_info_tab(self, parent, server_data):
        """Создание вкладки с информацией о сервере"""
        info_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        info_frame.pack(fill="both", expand=True)
        
        # Основная информация
        main_info = ctk.CTkFrame(info_frame, fg_color=("#ffffff", "#2b2b2b"), corner_radius=8)
        main_info.pack(fill="x", pady=10)
        
        info_content = ctk.CTkFrame(main_info, fg_color="transparent")
        info_content.pack(padx=20, pady=20)
        
        info_items = [
            ("ID сервера", server_data.get("id", "N/A")),
            ("Название", server_data.get("name", "N/A")),
            ("IP адрес", server_data.get("ip", "N/A")),
            ("SSH порт", server_data.get("ssh_port", 22)),
            ("SSH пользователь", server_data.get("ssh_user", "root")),
            ("Дата добавления", server_data.get("created_at", "N/A")[:10] if server_data.get("created_at") else "N/A")
        ]
        
        for label, value in info_items:
            row = ctk.CTkFrame(info_content, fg_color="transparent")
            row.pack(fill="x", pady=5)
            
            ctk.CTkLabel(
                row,
                text=label + ":",
                font=ctk.CTkFont(size=12),
                text_color=("#666666", "#aaaaaa"),
                width=150,
                anchor="w"
            ).pack(side="left")
            
            ctk.CTkLabel(
                row,
                text=str(value),
                font=ctk.CTkFont(size=12, weight="bold")
            ).pack(side="left")
        
        # FastPanel информация
        if server_data.get("fastpanel_installed"):
            fp_info = ctk.CTkFrame(info_frame, fg_color=("#ffffff", "#2b2b2b"), corner_radius=8)
            fp_info.pack(fill="x", pady=10)
            
            fp_content = ctk.CTkFrame(fp_info, fg_color="transparent")
            fp_content.pack(padx=20, pady=20)
            
            ctk.CTkLabel(
                fp_content,
                text="FastPanel",
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(anchor="w", pady=(0, 10))
            
            fp_items = [
                ("URL админ-панели", server_data.get("admin_url", "N/A")),
                ("Пароль администратора", "••••••••" if server_data.get("admin_password") else "Не сохранен")
            ]
            
            for label, value in fp_items:
                row = ctk.CTkFrame(fp_content, fg_color="transparent")
                row.pack(fill="x", pady=5)
                
                ctk.CTkLabel(
                    row,
                    text=label + ":",
                    font=ctk.CTkFont(size=12),
                    text_color=("#666666", "#aaaaaa"),
                    width=150,
                    anchor="w"
                ).pack(side="left")
                
                ctk.CTkLabel(
                    row,
                    text=str(value),
                    font=ctk.CTkFont(size=12)
                ).pack(side="left")
            
            # Кнопка показать пароль
            if server_data.get("admin_password"):
                show_pass_btn = ctk.CTkButton(
                    fp_content,
                    text="Показать пароль",
                    width=120,
                    height=28,
                    command=lambda: self.show_password(server_data["admin_password"])
                )
                show_pass_btn.pack(anchor="w", pady=(10, 0))
    
    def _create_sites_tab(self, parent, server_data):
        """Создание вкладки управления сайтами"""
        sites_frame = ctk.CTkFrame(parent, fg_color="transparent")
        sites_frame.pack(fill="both", expand=True)
        
        # Панель действий
        action_panel = ctk.CTkFrame(sites_frame, fg_color="transparent")
        action_panel.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(
            action_panel,
            text="➕ Добавить сайт",
            width=130,
            height=32,
            command=lambda: self.show_add_site_dialog(server_data)
        ).pack(side="left")
        
        # Список сайтов (пример)
        sites_list = ctk.CTkScrollableFrame(sites_frame, fg_color="transparent")
        sites_list.pack(fill="both", expand=True)
        
        # Пример сайтов
        example_sites = [
            {"domain": "example.com", "type": "PHP 8.1", "status": "active"},
            {"domain": "test.example.com", "type": "Node.js", "status": "active"},
            {"domain": "blog.example.com", "type": "WordPress", "status": "stopped"}
        ]
        
        for site in example_sites:
            site_card = ctk.CTkFrame(
                sites_list,
                fg_color=("#ffffff", "#2b2b2b"),
                corner_radius=8
            )
            site_card.pack(fill="x", pady=5)
            
            site_content = ctk.CTkFrame(site_card, fg_color="transparent")
            site_content.pack(padx=15, pady=12)
            
            # Информация о сайте
            ctk.CTkLabel(
                site_content,
                text=f"🌐 {site['domain']}",
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(anchor="w")
            
            ctk.CTkLabel(
                site_content,
                text=f"Тип: {site['type']} | Статус: {'✅' if site['status'] == 'active' else '⏸️'} {site['status']}",
                font=ctk.CTkFont(size=11),
                text_color=("#666666", "#aaaaaa")
            ).pack(anchor="w", pady=(2, 0))
    
    def _create_databases_tab(self, parent, server_data):
        """Создание вкладки управления базами данных"""
        db_frame = ctk.CTkFrame(parent, fg_color="transparent")
        db_frame.pack(fill="both", expand=True)
        
        ctk.CTkLabel(
            db_frame,
            text="🗄️ Управление базами данных",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=20)
        
        ctk.CTkLabel(
            db_frame,
            text="Функционал управления базами данных будет добавлен в следующей версии",
            font=ctk.CTkFont(size=12),
            text_color=("#666666", "#aaaaaa")
        ).pack()
    
    def _create_terminal_tab(self, parent, server_data):
        """Создание вкладки SSH терминала"""
        terminal_frame = ctk.CTkFrame(parent, fg_color="transparent")
        terminal_frame.pack(fill="both", expand=True)
        
        # Панель подключения
        connect_panel = ctk.CTkFrame(
            terminal_frame,
            fg_color=("#ffffff", "#2b2b2b"),
            corner_radius=8
        )
        connect_panel.pack(fill="x", pady=(0, 10))
        
        connect_content = ctk.CTkFrame(connect_panel, fg_color="transparent")
        connect_content.pack(padx=15, pady=10)
        
        ctk.CTkLabel(
            connect_content,
            text=f"SSH подключение к {server_data['ip']}",
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(0, 20))
        
        ctk.CTkButton(
            connect_content,
            text="🔌 Подключиться",
            width=120,
            height=28,
            fg_color=("#4caf50", "#2e7d32"),
            hover_color=("#45a049", "#1b5e20")
        ).pack(side="left")
        
        # Область терминала
        terminal_text = ctk.CTkTextbox(
            terminal_frame,
            font=ctk.CTkFont(family="Courier", size=11),
            fg_color=("#000000", "#000000"),
            text_color=("#00ff00", "#00ff00"),
            corner_radius=5
        )
        terminal_text.pack(fill="both", expand=True)
        
        terminal_text.insert("1.0", "$ SSH терминал будет доступен в следующей версии\n")
        terminal_text.insert("end", "$ Для подключения используйте внешний SSH клиент\n")
        terminal_text.configure(state="disabled")
    
    def show_install_dialog(self, server_data):
        """Диалог установки FastPanel"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Установка FastPanel")
        dialog.geometry("500x400")
        
        # Центрируем
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 250
        y = (dialog.winfo_screenheight() // 2) - 200
        dialog.geometry(f"500x400+{x}+{y}")
        
        # Содержимое
        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=30)
        
        ctk.CTkLabel(
            content,
            text="🚀 Установка FastPanel",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(0, 20))
        
        ctk.CTkLabel(
            content,
            text=f"Сервер: {server_data['name']} ({server_data['ip']})",
            font=ctk.CTkFont(size=12)
        ).pack(pady=(0, 20))
        
        # Поле для пароля
        ctk.CTkLabel(
            content,
            text="SSH пароль:",
            font=ctk.CTkFont(size=12),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        password_entry = ctk.CTkEntry(
            content,
            placeholder_text="Введите SSH пароль",
            show="*",
            height=40
        )
        password_entry.pack(fill="x", pady=(0, 20))
        
        # Прогресс бар
        progress = ctk.CTkProgressBar(content)
        progress.pack(fill="x", pady=10)
        progress.set(0)
        
        # Лог установки
        log_text = ctk.CTkTextbox(
            content,
            height=150,
            font=ctk.CTkFont(size=10)
        )
        log_text.pack(fill="both", expand=True, pady=(10, 20))
        
        # Кнопки
        buttons_frame = ctk.CTkFrame(content, fg_color="transparent")
        buttons_frame.pack(fill="x")
        
        cancel_btn = ctk.CTkButton(
            buttons_frame,
            text="Отмена",
            width=100,
            fg_color="transparent",
            border_width=1,
            text_color=("#000000", "#ffffff"),
            border_color=("#e0e0e0", "#404040"),
            command=dialog.destroy
        )
        cancel_btn.pack(side="left", padx=(0, 10))
        
        install_btn = ctk.CTkButton(
            buttons_frame,
            text="Начать установку",
            width=150,
            command=lambda: self.start_installation(server_data, password_entry.get(), log_text, progress)
        )
        install_btn.pack(side="left")
    
    def show_add_site_dialog(self, server_data):
        """Диалог добавления сайта"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Добавление сайта")
        dialog.geometry("500x450")
        
        # Центрируем
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 250
        y = (dialog.winfo_screenheight() // 2) - 225
        dialog.geometry(f"500x450+{x}+{y}")
        
        # Форма
        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=30, pady=30)
        
        ctk.CTkLabel(
            form,
            text="🌐 Новый сайт",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(0, 20))
        
        # Домен
        ctk.CTkLabel(
            form,
            text="Домен:",
            font=ctk.CTkFont(size=12),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        domain_entry = ctk.CTkEntry(
            form,
            placeholder_text="example.com",
            height=40
        )
        domain_entry.pack(fill="x", pady=(0, 15))
        
        # Тип сайта
        ctk.CTkLabel(
            form,
            text="Тип сайта:",
            font=ctk.CTkFont(size=12),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        site_type = ctk.CTkOptionMenu(
            form,
            values=["PHP", "Node.js", "Python", "Static", "WordPress"],
            height=40
        )
        site_type.pack(fill="x", pady=(0, 15))
        
        # Версия PHP (если выбран PHP)
        ctk.CTkLabel(
            form,
            text="Версия PHP:",
            font=ctk.CTkFont(size=12),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        php_version = ctk.CTkOptionMenu(
            form,
            values=["8.3", "8.2", "8.1", "8.0", "7.4"],
            height=40
        )
        php_version.pack(fill="x", pady=(0, 15))
        
        # SSL
        ssl_switch = ctk.CTkSwitch(
            form,
            text="Включить SSL (Let's Encrypt)",
            font=ctk.CTkFont(size=12)
        )
        ssl_switch.pack(anchor="w", pady=10)
        
        # Кнопки
        buttons_frame = ctk.CTkFrame(form, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=(20, 0))
        
        ctk.CTkButton(
            buttons_frame,
            text="Отмена",
            width=100,
            fg_color="transparent",
            border_width=1,
            text_color=("#000000", "#ffffff"),
            border_color=("#e0e0e0", "#404040"),
            command=dialog.destroy
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            buttons_frame,
            text="Создать сайт",
            width=150
        ).pack(side="left")
    
    def confirm_delete_server(self, server_data):
        """Подтверждение удаления сервера"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Подтверждение удаления")
        dialog.geometry("400x200")
        
        # Центрируем
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 200
        y = (dialog.winfo_screenheight() // 2) - 100
        dialog.geometry(f"400x200+{x}+{y}")
        
        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=30)
        
        ctk.CTkLabel(
            content,
            text="⚠️ Удаление сервера",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#f44336", "#f44336")
        ).pack(pady=(0, 20))
        
        ctk.CTkLabel(
            content,
            text=f"Вы уверены, что хотите удалить сервер\n{server_data['name']} ({server_data['ip']})?",
            font=ctk.CTkFont(size=12)
        ).pack(pady=(0, 30))
        
        buttons_frame = ctk.CTkFrame(content, fg_color="transparent")
        buttons_frame.pack()
        
        ctk.CTkButton(
            buttons_frame,
            text="Отмена",
            width=100,
            fg_color="transparent",
            border_width=1,
            text_color=("#000000", "#ffffff"),
            border_color=("#e0e0e0", "#404040"),
            command=dialog.destroy
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            buttons_frame,
            text="Удалить",
            width=100,
            fg_color=("#f44336", "#d32f2f"),
            hover_color=("#da190b", "#b71c1c"),
            command=lambda: self.delete_server(server_data, dialog)
        ).pack(side="left")
    
    def show_password(self, password):
        """Показать пароль в диалоге"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Пароль администратора")
        dialog.geometry("400x150")
        
        # Центрируем
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 200
        y = (dialog.winfo_screenheight() // 2) - 75
        dialog.geometry(f"400x150+{x}+{y}")
        
        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=30)
        
        ctk.CTkLabel(
            content,
            text="Пароль администратора FastPanel:",
            font=ctk.CTkFont(size=12)
        ).pack(pady=(0, 10))
        
        password_frame = ctk.CTkFrame(
            content,
            fg_color=("#f5f5f5", "#1a1a1a"),
            corner_radius=5
        )
        password_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            password_frame,
            text=password,
            font=ctk.CTkFont(family="Courier", size=14, weight="bold")
        ).pack(padx=10, pady=10)
        
        ctk.CTkButton(
            content,
            text="Закрыть",
            width=100,
            command=dialog.destroy
        ).pack(pady=(10, 0))
    
    def add_server(self):
        """Добавление нового сервера"""
        import uuid
        from datetime import datetime
        
        # Получаем данные из полей
        name = self.server_name_entry.get()
        ip = self.server_ip_entry.get()
        port = self.server_port_entry.get() or "22"
        user = self.server_user_entry.get() or "root"
        
        if not name or not ip:
            self.show_error("Заполните обязательные поля")
            return
        
        # Создаем новый сервер
        new_server = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "ip": ip,
            "ssh_port": int(port),
            "ssh_user": user,
            "fastpanel_installed": False,
            "admin_url": None,
            "admin_password": None,
            "created_at": datetime.now().isoformat()
        }
        
        # Добавляем в список
        self.servers.append(new_server)
        self.save_servers()
        
        # Показываем уведомление
        self.show_success(f"Сервер {name} успешно добавлен")
        
        # Возвращаемся к списку серверов
        self.show_servers_tab()
    
    def delete_server(self, server_data, dialog):
        """Удаление сервера"""
        self.servers = [s for s in self.servers if s["id"] != server_data["id"]]
        self.save_servers()
        dialog.destroy()
        self.show_success(f"Сервер {server_data['name']} удален")
        self.show_servers_tab()
    
    def start_installation(self, server_data, password, log_widget, progress_widget):
        """Начать установку FastPanel (заглушка)"""
        log_widget.insert("end", "🚀 Начинаем установку FastPanel...\n")
        log_widget.insert("end", f"📡 Подключение к {server_data['ip']}...\n")
        progress_widget.set(0.2)
        
        # Здесь будет реальная установка через SSH
        log_widget.insert("end", "✅ Подключение установлено\n")
        log_widget.insert("end", "📦 Загрузка установщика...\n")
        progress_widget.set(0.5)
        
        log_widget.insert("end", "⚙️ Установка FastPanel...\n")
        log_widget.insert("end", "⏳ Это может занять несколько минут...\n")
        progress_widget.set(0.8)
        
        # Симуляция завершения
        self.after(2000, lambda: self._complete_installation(server_data, log_widget, progress_widget))
    
    def _complete_installation(self, server_data, log_widget, progress_widget):
        """Завершение установки (заглушка)"""
        log_widget.insert("end", "\n✅ FastPanel успешно установлен!\n")
        log_widget.insert("end", f"🔗 URL: https://{server_data['ip']}:8888\n")
        log_widget.insert("end", "🔑 Пароль: [будет здесь]\n")
        progress_widget.set(1.0)
        
        # Обновляем данные сервера
        for server in self.servers:
            if server["id"] == server_data["id"]:
                server["fastpanel_installed"] = True
                server["admin_url"] = f"https://{server_data['ip']}:8888"
                break
        
        self.save_servers()
    
    def load_servers(self):
        """Загрузка списка серверов"""
        try:
            data_file = Path("data/servers.json")
            if data_file.exists():
                with open(data_file, 'r') as f:
                    self.servers = json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки серверов: {e}")
            self.servers = []
    
    def save_servers(self):
        """Сохранение списка серверов"""
        try:
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            
            with open(data_dir / "servers.json", 'w') as f:
                json.dump(self.servers, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения серверов: {e}")
    
    def refresh_data(self):
        """Обновление данных"""
        self.load_servers()
        
        # Обновляем текущую вкладку
        if self.current_tab == "servers":
            self.show_servers_tab()
        
        self.show_success("Данные обновлены")
    
    def show_success(self, message):
        """Показать уведомление об успехе"""
        self.status_label.configure(
            text=f"✅ {message}",
            text_color=("#4caf50", "#4caf50")
        )
        # Сбросить через 3 секунды
        self.after(3000, lambda: self.status_label.configure(
            text="● Готов к работе",
            text_color=("#4caf50", "#4caf50")
        ))
    
    def show_error(self, message):
        """Показать уведомление об ошибке"""
        self.status_label.configure(
            text=f"❌ {message}",
            text_color=("#f44336", "#f44336")
        )
        # Сбросить через 3 секунды
        self.after(3000, lambda: self.status_label.configure(
            text="● Готов к работе",
            text_color=("#4caf50", "#4caf50")
        ))


def main():
    """Точка входа для GUI приложения"""
    app = FastPanelApp()
    app.mainloop()


if __name__ == "__main__":
    main()
