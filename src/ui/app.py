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
import sys
import uuid
import webbrowser

# Настройка внешнего вида
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ServerCard(ctk.CTkFrame):
    """Карточка сервера для отображения в списке"""

    def __init__(self, parent, server_data: dict, on_click=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.server_data = server_data
        self.on_click = on_click

        self.configure(
            corner_radius=10,
            fg_color=("#ffffff", "#2b2b2b"),
            border_width=1,
            border_color=("#e0e0e0", "#404040")
        )

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=15, pady=12)

        top_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_frame.pack(fill="x", pady=(0, 8))

        server_icon = ctk.CTkLabel(top_frame, text="🖥️", font=ctk.CTkFont(size=24))
        server_icon.pack(side="left", padx=(0, 10))

        info_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)

        name_label = ctk.CTkLabel(info_frame, text=self.server_data.get("name", "Безымянный сервер"), font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        name_label.pack(fill="x")

        ip_label = ctk.CTkLabel(info_frame, text=f"IP: {self.server_data.get('ip', 'Не указан')}", font=ctk.CTkFont(size=12), text_color=("#666666", "#aaaaaa"), anchor="w")
        ip_label.pack(fill="x")

        status_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        status_frame.pack(side="right")

        if self.server_data.get("fastpanel_installed"):
            status_badge = ctk.CTkLabel(status_frame, text="✅ FastPanel установлен", font=ctk.CTkFont(size=11), fg_color=("#4caf50", "#2e7d32"), corner_radius=5, text_color="white")
            status_badge.pack(padx=8, pady=4)
        else:
            status_badge = ctk.CTkLabel(status_frame, text="⏳ Не установлен", font=ctk.CTkFont(size=11), fg_color=("#ff9800", "#f57c00"), corner_radius=5, text_color="white")
            status_badge.pack(padx=8, pady=4)

        separator = ctk.CTkFrame(main_frame, height=1, fg_color=("#e0e0e0", "#404040"))
        separator.pack(fill="x", pady=8)

        bottom_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        bottom_frame.pack(fill="x")

        if self.server_data.get("fastpanel_installed"):
            manage_btn = ctk.CTkButton(bottom_frame, text="Управление", width=100, height=28, font=ctk.CTkFont(size=12), command=lambda: self._on_manage())
            manage_btn.pack(side="left", padx=(0, 5))
            panel_btn = ctk.CTkButton(bottom_frame, text="Открыть панель", width=100, height=28, font=ctk.CTkFont(size=12), fg_color=("#4caf50", "#2e7d32"), hover_color=("#45a049", "#1b5e20"), command=lambda: self._open_panel())
            panel_btn.pack(side="left", padx=5)
        else:
            install_btn = ctk.CTkButton(bottom_frame, text="Установить FastPanel", width=150, height=28, font=ctk.CTkFont(size=12), fg_color=("#2196f3", "#1976d2"), hover_color=("#1976d2", "#1565c0"), command=lambda: self._on_install())
            install_btn.pack(side="left")

        delete_btn = ctk.CTkButton(bottom_frame, text="🗑️", width=30, height=28, fg_color=("#f44336", "#d32f2f"), hover_color=("#da190b", "#b71c1c"), command=lambda: self._on_delete())
        delete_btn.pack(side="right")

        edit_btn = ctk.CTkButton(bottom_frame, text="✏️", width=30, height=28, command=lambda: self._on_edit())
        edit_btn.pack(side="right", padx=5)


    def _on_manage(self):
        if self.on_click: self.on_click("manage", self.server_data)

    def _on_install(self):
        if self.on_click: self.on_click("install", self.server_data)

    def _open_panel(self):
        if self.on_click: self.on_click("open_panel", self.server_data)

    def _on_delete(self):
        if self.on_click: self.on_click("delete", self.server_data)

    def _on_edit(self):
        if self.on_click: self.on_click("edit", self.server_data)

class FastPanelApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FastPanel Automation")
        self.geometry("1200x700")
        self.minsize(1000, 600)
        self.center_window()

        self.servers = []
        self.domains = []
        self.logs = []
        self.current_tab = "servers"

        self.log_action("Приложение запущено")

        self._create_widgets()
        self.load_servers()
        self.load_domains()
        
        self._update_server_list() # Первоначальное отображение серверов

        if sys.platform == "darwin" and os.path.exists("assets/icon.icns"):
            self.iconbitmap("assets/icon.icns")

    def center_window(self):
        self.update_idletasks()
        width, height = 1200, 700
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def _create_widgets(self):
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True)

        self._create_sidebar(main_container)

        self.content_frame = ctk.CTkFrame(main_container, fg_color=("#f5f5f5", "#1a1a1a"), corner_radius=0)
        self.content_frame.pack(side="right", fill="both", expand=True)

        self._create_header()

        self.tab_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.show_servers_tab()

    def _create_sidebar(self, parent):
        self.sidebar = ctk.CTkFrame(parent, width=250, fg_color=("#ffffff", "#2b2b2b"), corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(logo_frame, text="🚀 FastPanel", font=ctk.CTkFont(size=24, weight="bold")).pack()
        ctk.CTkLabel(logo_frame, text="Automation Tool", font=ctk.CTkFont(size=12), text_color=("#666666", "#aaaaaa")).pack()

        ctk.CTkFrame(self.sidebar, height=2, fg_color=("#e0e0e0", "#404040")).pack(fill="x", padx=20, pady=10)

        nav_buttons = [
            ("🖥️", "Серверы", self.show_servers_tab),
            ("🌐", "Домены", self.show_domain_tab),
            ("☁️", "Cloudflare", self.show_cloudflare_tab),
            ("🔧", "Настройки", self.show_settings_tab),
            ("📊", "Мониторинг", self.show_monitoring_tab),
            ("📝", "Логи", self.show_logs_tab),
            ("📋", "Результат", self.show_result_tab),
        ]

        for icon, text, command in nav_buttons:
            ctk.CTkButton(self.sidebar, text=f"{icon}  {text}", font=ctk.CTkFont(size=14), height=40, fg_color="transparent", text_color=("#000000", "#ffffff"), hover_color=("#e0e0e0", "#404040"), anchor="w", command=command).pack(fill="x", padx=15, pady=2)

        info_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        info_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkLabel(info_frame, text="Version 0.2.2", font=ctk.CTkFont(size=10), text_color=("#999999", "#666666")).pack()
        self.status_label = ctk.CTkLabel(info_frame, text="● Готов к работе", font=ctk.CTkFont(size=11), text_color=("#4caf50", "#4caf50"))
        self.status_label.pack(pady=(5, 0))

    def _create_header(self):
        header_frame = ctk.CTkFrame(self.content_frame, height=80, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        header_frame.pack_propagate(False)

        self.page_title = ctk.CTkLabel(header_frame, text="Управление серверами", font=ctk.CTkFont(size=28, weight="bold"))
        self.page_title.pack(side="left")

        ctk.CTkButton(header_frame, text="🔄 Обновить", width=100, height=32, font=ctk.CTkFont(size=12), fg_color=("#2196f3", "#1976d2"), hover_color=("#1976d2", "#1565c0"), command=self.refresh_data).pack(side="right", padx=(10, 0))
        
        self.search_entry = ctk.CTkEntry(header_frame, placeholder_text="🔍 Поиск серверов...", width=250, height=32, font=ctk.CTkFont(size=12))
        self.search_entry.pack(side="right", padx=10)
        self.search_entry.bind("<KeyRelease>", self._update_server_list)

    def show_servers_tab(self):
        self.clear_tab_container()
        self.page_title.configure(text="Управление серверами")
        self.current_tab = "servers"

        top_panel = ctk.CTkFrame(self.tab_container, fg_color="transparent")
        top_panel.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(top_panel, text="➕ Добавить сервер", font=ctk.CTkFont(size=14, weight="bold"), width=200, height=40, command=self.show_add_server_tab, fg_color="#2196f3", hover_color="#1976d2").pack(side="left")

        self.scrollable_servers = ctk.CTkScrollableFrame(self.tab_container, fg_color="transparent")
        self.scrollable_servers.pack(fill="both", expand=True)

        self._update_server_list()

    def _update_server_list(self, event=None):
        if not hasattr(self, 'scrollable_servers'): return # Выход если виджет еще не создан
        for widget in self.scrollable_servers.winfo_children():
            widget.destroy()

        search_query = self.search_entry.get().lower()
        sorted_servers = sorted(self.servers, key=lambda s: s.get('created_at', ''), reverse=True)
        filtered_servers = [s for s in sorted_servers if search_query in s.get("name", "").lower() or search_query in s.get("ip", "").lower()]

        if not filtered_servers:
            empty_frame = ctk.CTkFrame(self.scrollable_servers, fg_color="transparent")
            empty_frame.pack(expand=True, pady=50)
            ctk.CTkLabel(empty_frame, text="📭", font=ctk.CTkFont(size=64)).pack()
            ctk.CTkLabel(empty_frame, text="Нет добавленных серверов", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 10))
            ctk.CTkLabel(empty_frame, text="Добавьте первый сервер, чтобы начать работу", font=ctk.CTkFont(size=14), text_color=("#666666", "#aaaaaa")).pack()
        else:
            for server in filtered_servers:
                ServerCard(self.scrollable_servers, server, on_click=self.handle_server_action).pack(fill="x", pady=5)

    def show_add_server_tab(self, server_data=None):
        self.clear_tab_container()
        is_editing = server_data is not None
        self.page_title.configure(text="Редактирование сервера" if is_editing else "Добавление нового сервера")
        self.current_tab = "add_server"

        scrollable_form = ctk.CTkScrollableFrame(self.tab_container, fg_color="transparent")
        scrollable_form.pack(fill="both", expand=True)

        form_frame = ctk.CTkFrame(scrollable_form, fg_color=("#ffffff", "#2b2b2b"), corner_radius=10)
        form_frame.pack(fill="both", expand=True, padx=100, pady=50)

        ctk.CTkLabel(form_frame, text="Параметры сервера", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(30, 20))
        
        server_type_var = ctk.StringVar(value="new")
        if is_editing:
            server_type = "existing" if server_data.get("fastpanel_installed") else "new"
            server_type_var.set(server_type)

        radio_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        radio_frame.pack(pady=10)

        new_radio = ctk.CTkRadioButton(radio_frame, text="Новая установка", variable=server_type_var, value="new", command=lambda: self.toggle_server_form(server_type_var.get(), form_frame, server_data if server_type_var.get() == "new" else None))
        new_radio.pack(side="left", padx=10)

        existing_radio = ctk.CTkRadioButton(radio_frame, text="Существующий FastPanel", variable=server_type_var, value="existing", command=lambda: self.toggle_server_form(server_type_var.get(), form_frame, server_data if server_type_var.get() == "existing" else None))
        existing_radio.pack(side="left", padx=10)

        if is_editing:
             new_radio.configure(state="disabled")
             existing_radio.configure(state="disabled")

        self.toggle_server_form(server_type_var.get(), form_frame, server_data)

    def toggle_server_form(self, server_type, parent_frame, server_data=None):
        if hasattr(self, "fields_frame"): self.fields_frame.destroy()
        if hasattr(self, "buttons_frame"): self.buttons_frame.destroy()

        self.fields_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        self.fields_frame.pack(padx=50, pady=20, fill="x", expand=True)

        if server_type == "new":
            self.create_new_server_form(self.fields_frame, server_data)
        else:
            self.create_existing_server_form(self.fields_frame, server_data)

        self.buttons_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        self.buttons_frame.pack(pady=(10, 30))

        ctk.CTkButton(self.buttons_frame, text="Отмена", width=120, height=40, fg_color="transparent", border_width=1, text_color=("#000000", "#ffffff"), border_color=("#e0e0e0", "#404040"), hover_color=("#f0f0f0", "#333333"), command=self.show_servers_tab).pack(side="left", padx=5)
        ctk.CTkButton(self.buttons_frame, text="Сохранить", width=150, height=40, font=ctk.CTkFont(size=13, weight="bold"), command=lambda: self.add_or_update_server(server_type, server_data)).pack(side="left", padx=5)


    def create_new_server_form(self, parent, data=None):
        ctk.CTkLabel(parent, text="Название сервера", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.server_name_entry = ctk.CTkEntry(parent, width=400, height=40)
        self.server_name_entry.pack(pady=(0, 15), fill="x", expand=True)
        if data: self.server_name_entry.insert(0, data.get("name", ""))

        ctk.CTkLabel(parent, text="IP адрес", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.server_ip_entry = ctk.CTkEntry(parent, width=400, height=40)
        self.server_ip_entry.pack(pady=(0, 15), fill="x", expand=True)
        if data: self.server_ip_entry.insert(0, data.get("ip", ""))

        ctk.CTkLabel(parent, text="Пользователь", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.server_user_entry = ctk.CTkEntry(parent, width=400, height=40)
        self.server_user_entry.pack(pady=(0, 15), fill="x", expand=True)
        self.server_user_entry.insert(0, data.get("ssh_user", "root") if data else "root")

        ctk.CTkLabel(parent, text="Пароль", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.server_password_entry = ctk.CTkEntry(parent, width=400, height=40, show="*")
        self.server_password_entry.pack(pady=(0, 15), fill="x", expand=True)
        if data: self.server_password_entry.insert(0, data.get("password", ""))

        ctk.CTkLabel(parent, text="Дата окончания (YYYY-MM-DD)", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.server_expiration_entry = ctk.CTkEntry(parent, width=400, height=40)
        self.server_expiration_entry.pack(pady=(0, 15), fill="x", expand=True)
        if data: self.server_expiration_entry.insert(0, data.get("expiration_date", ""))

    def create_existing_server_form(self, parent, data=None):
        ctk.CTkLabel(parent, text="Имя сервера", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.existing_server_name_entry = ctk.CTkEntry(parent, width=400, height=40)
        self.existing_server_name_entry.pack(pady=(0, 15), fill="x", expand=True)
        if data: self.existing_server_name_entry.insert(0, data.get("name", ""))

        ctk.CTkLabel(parent, text="URL панели (https://ip:8888)", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.server_url_entry = ctk.CTkEntry(parent, width=400, height=40)
        self.server_url_entry.pack(pady=(0, 15), fill="x", expand=True)
        if data: self.server_url_entry.insert(0, data.get("admin_url", ""))
        
        ctk.CTkLabel(parent, text="Пароль", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.fastuser_password_entry = ctk.CTkEntry(parent, width=400, height=40, show="*")
        self.fastuser_password_entry.pack(pady=(0, 15), fill="x", expand=True)
        if data: self.fastuser_password_entry.insert(0, data.get("admin_password", ""))
        
        ctk.CTkLabel(parent, text="Дата окончания (YYYY-MM-DD)", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.existing_server_expiration_entry = ctk.CTkEntry(parent, width=400, height=40)
        self.existing_server_expiration_entry.pack(pady=(0, 15), fill="x", expand=True)
        if data: self.existing_server_expiration_entry.insert(0, data.get("expiration_date", ""))


    def show_domain_tab(self):
        self.clear_tab_container()
        self.page_title.configure(text="Управление доменами")
        self.current_tab = "domain"

        top_panel = ctk.CTkFrame(self.tab_container, fg_color="transparent")
        top_panel.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(top_panel, text="➕ Добавить домен(-ы)", command=self.show_add_domain_dialog).pack(side="left")

        domain_list_frame = ctk.CTkScrollableFrame(self.tab_container, fg_color="transparent")
        domain_list_frame.pack(fill="both", expand=True)

        if not self.domains:
            ctk.CTkLabel(domain_list_frame, text="Нет добавленных доменов").pack(pady=20)
        else:
            for idx, domain_info in enumerate(self.domains):
                domain_frame = ctk.CTkFrame(domain_list_frame, fg_color=("#ffffff", "#2b2b2b"), corner_radius=8)
                domain_frame.pack(fill="x", pady=5, padx=5)
                ctk.CTkLabel(domain_frame, text=f"🌐 {domain_info['domain']}", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=10, pady=10)
                
                server_ips = ["(Не выбран)"] + [s['ip'] for s in self.servers if s.get('ip')]
                server_var = ctk.StringVar(value=domain_info.get("server_ip") or "(Не выбран)")
                server_menu = ctk.CTkOptionMenu(domain_frame, values=server_ips, variable=server_var, command=lambda ip, i=idx: self.update_domain_server(i, ip))
                server_menu.pack(side="right", padx=10, pady=10)
    
    def show_add_domain_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Добавить домены")
        dialog.geometry("500x450")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Добавить домены", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)
        ctk.CTkLabel(dialog, text="Введите домены (каждый с новой строки):").pack()
        domain_textbox = ctk.CTkTextbox(dialog, height=200, width=400)
        domain_textbox.pack(pady=10)

        ctk.CTkButton(dialog, text="Сохранить", command=lambda: self.add_domains(domain_textbox.get("1.0", "end-1c"), dialog)).pack(pady=20)

    def add_domains(self, domains_text, dialog):
        domains = [d.strip() for d in domains_text.split("\n") if d.strip()]
        added_count = 0
        for domain in domains:
            if not any(d['domain'] == domain for d in self.domains):
                self.domains.append({"domain": domain, "server_ip": ""})
                added_count += 1
        
        if added_count > 0:
            self.log_action(f"Добавлено {added_count} доменов")
            self.save_domains()
            self.show_domain_tab()

        dialog.destroy()

    def update_domain_server(self, index, server_ip):
        ip_to_save = server_ip if server_ip != "(Не выбран)" else ""
        self.domains[index]["server_ip"] = ip_to_save
        self.save_domains()
        self.log_action(f"Для домена {self.domains[index]['domain']} установлен сервер {server_ip}")
        self.show_success(f"Сервер для домена обновлен")
        
    def show_result_tab(self):
        self.clear_tab_container()
        self.page_title.configure(text="Результаты установки")
        self.current_tab = "result"
        result_textbox = ctk.CTkTextbox(self.tab_container, wrap="word")
        result_textbox.pack(fill="both", expand=True)
        result_text = ""
        for server in self.servers:
            if server.get("fastpanel_installed"):
                result_text += f"{server['ip']};user{server['id']};pass{server['id']}\n"
        result_textbox.insert("1.0", result_text or "Нет данных для отображения.")
        result_textbox.configure(state="disabled")

    def show_cloudflare_tab(self):
        self.clear_tab_container()
        self.page_title.configure(text="Интеграция с Cloudflare")
        self.current_tab = "cloudflare"
        ctk.CTkLabel(self.tab_container, text="Вкладка Cloudflare", font=("Arial", 24)).pack(pady=20)

    def show_settings_tab(self):
        self.clear_tab_container()
        self.page_title.configure(text="Настройки")
        self.current_tab = "settings"
        ctk.CTkLabel(self.tab_container, text="Вкладка настроек", font=("Arial", 24)).pack(pady=20)

    def show_monitoring_tab(self):
        self.clear_tab_container()
        self.page_title.configure(text="Мониторинг")
        self.current_tab = "monitoring"
        ctk.CTkLabel(self.tab_container, text="Вкладка мониторинга", font=("Arial", 24)).pack(pady=20)

    def show_logs_tab(self):
        self.clear_tab_container()
        self.page_title.configure(text="Логи")
        self.current_tab = "logs"
        
        logs_text = ctk.CTkTextbox(self.tab_container, wrap="word")
        logs_text.pack(fill="both", expand=True)
        
        logs_text.insert("1.0", "\n".join(self.logs))
        logs_text.configure(state="disabled")

    def _create_settings_section(self, parent, title, description):
        section = ctk.CTkFrame(parent, fg_color=("#ffffff", "#2b2b2b"), corner_radius=10)
        section.pack(fill="x", pady=10)
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text=description, font=ctk.CTkFont(size=11), text_color=("#666666", "#aaaaaa")).pack(anchor="w", pady=(2, 0))
        return section

    def _add_setting_field(self, parent, label, widget):
        field_frame = ctk.CTkFrame(parent, fg_color="transparent")
        field_frame.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(field_frame, text=label, font=ctk.CTkFont(size=12), width=150, anchor="w").pack(side="left")
        widget.configure(width=250)
        widget.pack(side="left", padx=(20, 0))

    def clear_tab_container(self):
        for widget in self.tab_container.winfo_children():
            widget.destroy()

    def handle_server_action(self, action, server_data):
        actions = {
            "manage": self.show_server_management,
            "install": self.show_install_dialog,
            "open_panel": lambda s: webbrowser.open(s.get("admin_url")) if s.get("admin_url") else None,
            "delete": self.confirm_delete_server,
            "edit": self.show_add_server_tab,
        }
        if action in actions:
            actions[action](server_data)

    def show_server_management(self, server_data):
        manage_window = ctk.CTkToplevel(self)
        manage_window.title(f"Управление: {server_data['name']}")
        manage_window.geometry("800x600")
        manage_window.transient(self)
        manage_window.grab_set()

        header = ctk.CTkFrame(manage_window, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(header, text=f"🖥️ {server_data['name']}", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text=f"IP: {server_data['ip']} | Статус: {'✅ FastPanel установлен' if server_data.get('fastpanel_installed') else '⏳ Не установлен'}", font=ctk.CTkFont(size=12), text_color=("#666666", "#aaaaaa")).pack(anchor="w", pady=(5, 0))

        tabview = ctk.CTkTabview(manage_window)
        tabview.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self._create_server_info_tab(tabview.add("Информация"), server_data)
        self._create_sites_tab(tabview.add("Сайты"), server_data)
        self._create_databases_tab(tabview.add("Базы данных"), server_data)
        self._create_terminal_tab(tabview.add("SSH Терминал"), server_data)

    def _create_server_info_tab(self, parent, data):
        info_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        info_frame.pack(fill="both", expand=True)
        main_info = ctk.CTkFrame(info_frame, fg_color=("#ffffff", "#2b2b2b"), corner_radius=8)
        main_info.pack(fill="x", pady=10)
        info_content = ctk.CTkFrame(main_info, fg_color="transparent")
        info_content.pack(padx=20, pady=20)
        info_items = [
            ("ID", data.get("id")), ("Название", data.get("name")), ("IP", data.get("ip")),
            ("SSH порт", data.get("ssh_port", 22)), ("SSH пользователь", data.get("ssh_user")),
            ("Дата добавления", data.get("created_at", "N/A")[:10])
        ]
        for label, value in info_items:
            row = ctk.CTkFrame(info_content, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=f"{label}:", width=150, anchor="w", text_color=("#666666", "#aaaaaa")).pack(side="left")
            ctk.CTkLabel(row, text=str(value), font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        if data.get("fastpanel_installed"):
            fp_info = ctk.CTkFrame(info_frame, fg_color=("#ffffff", "#2b2b2b"), corner_radius=8)
            fp_info.pack(fill="x", pady=10)
            fp_content = ctk.CTkFrame(fp_info, fg_color="transparent")
            fp_content.pack(padx=20, pady=20)
            ctk.CTkLabel(fp_content, text="FastPanel", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(0, 10))
            fp_items = [
                ("URL", data.get("admin_url", f"https://{data.get('ip')}:8888")),
                ("Логин", "fastuser"),
                ("Пароль", "••••••••" if data.get("admin_password") else "Не сохранен")
            ]
            for label, value in fp_items:
                row = ctk.CTkFrame(fp_content, fg_color="transparent")
                row.pack(fill="x", pady=5)
                ctk.CTkLabel(row, text=f"{label}:", width=150, anchor="w", text_color=("#666666", "#aaaaaa")).pack(side="left")
                ctk.CTkLabel(row, text=str(value)).pack(side="left")


    def _create_sites_tab(self, parent, server_data):
        sites_frame = ctk.CTkFrame(parent, fg_color="transparent")
        sites_frame.pack(fill="both", expand=True)
        
        sites_list_frame = ctk.CTkScrollableFrame(sites_frame, fg_color="transparent")
        sites_list_frame.pack(fill="both", expand=True)

        server_domains = [d for d in self.domains if d.get("server_ip") == server_data.get("ip")]

        if not server_domains:
            ctk.CTkLabel(sites_list_frame, text="На этом сервере нет сайтов").pack(pady=20)
        else:
            for domain_info in server_domains:
                site_card = ctk.CTkFrame(sites_list_frame, fg_color=("#ffffff", "#2b2b2b"), corner_radius=8)
                site_card.pack(fill="x", pady=5)
                site_content = ctk.CTkFrame(site_card, fg_color="transparent")
                site_content.pack(padx=15, pady=12, fill="x")
                
                ctk.CTkLabel(site_content, text=f"🌐 {domain_info['domain']}", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", anchor="w")
                
                delete_button = ctk.CTkButton(site_content, text="🗑️", width=30, height=28, fg_color=("#f44336", "#d32f2f"), hover_color=("#da190b", "#b71c1c"), command=lambda d=domain_info: self.delete_domain_from_server(d, server_data))
                delete_button.pack(side="right", anchor="e")


    def _create_databases_tab(self, parent, server_data):
        db_frame = ctk.CTkFrame(parent, fg_color="transparent")
        db_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(db_frame, text="🗄️ Управление базами данных", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=20)
        ctk.CTkLabel(db_frame, text="Функционал управления базами данных будет добавлен в следующей версии", font=ctk.CTkFont(size=12), text_color=("#666666", "#aaaaaa")).pack()

    def _create_terminal_tab(self, parent, server_data):
        terminal_frame = ctk.CTkFrame(parent, fg_color="transparent")
        terminal_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(terminal_frame, text="SSH Терминал", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=20)
        ctk.CTkLabel(terminal_frame, text="Функционал терминала будет добавлен в следующей версии", font=ctk.CTkFont(size=12), text_color=("#666666", "#aaaaaa")).pack()

    def show_install_dialog(self, server_data):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Установка FastPanel")
        dialog.geometry("600x550")
        dialog.transient(self)
        dialog.grab_set()

        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=30)
        ctk.CTkLabel(content, text="🚀 Установка FastPanel", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(0, 20))
        ctk.CTkLabel(content, text=f"Сервер: {server_data['name']} ({server_data['ip']})", font=ctk.CTkFont(size=12)).pack(pady=(0, 20))
        
        password_entry = ctk.CTkEntry(content, placeholder_text="Введите SSH пароль", show="*", height=40)
        password_entry.pack(fill="x", pady=(0, 20))
        if server_data.get("password"): password_entry.insert(0, server_data["password"])

        progress = ctk.CTkProgressBar(content)
        progress.pack(fill="x", pady=10)
        progress.set(0)
        log_text = ctk.CTkTextbox(content, height=150, font=ctk.CTkFont(size=10))
        log_text.pack(fill="both", expand=True, pady=(10, 20))
        buttons_frame = ctk.CTkFrame(content, fg_color="transparent")
        buttons_frame.pack(fill="x")
        ctk.CTkButton(buttons_frame, text="Отмена", width=100, fg_color="transparent", border_width=1, text_color=("#000000", "#ffffff"), border_color=("#e0e0e0", "#404040"), command=dialog.destroy).pack(side="left", padx=(0, 10))
        ctk.CTkButton(buttons_frame, text="Начать установку", width=150, command=lambda: self.start_installation(server_data, password_entry.get(), log_text, progress)).pack(side="left")

    def confirm_delete_server(self, server_data):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Подтверждение удаления")
        dialog.geometry("400x200")
        dialog.transient(self)
        dialog.grab_set()
        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=30)
        ctk.CTkLabel(content, text="⚠️ Удаление сервера", font=ctk.CTkFont(size=18, weight="bold"), text_color=("#f44336", "#f44336")).pack(pady=(0, 20))
        ctk.CTkLabel(content, text=f"Вы уверены, что хотите удалить сервер\n{server_data['name']} ({server_data['ip']})?", font=ctk.CTkFont(size=12)).pack(pady=(0, 30))
        buttons_frame = ctk.CTkFrame(content, fg_color="transparent")
        buttons_frame.pack()
        ctk.CTkButton(buttons_frame, text="Отмена", width=100, fg_color="transparent", border_width=1, text_color=("#000000", "#ffffff"), border_color=("#e0e0e0", "#404040"), command=dialog.destroy).pack(side="left", padx=(0, 10))
        ctk.CTkButton(buttons_frame, text="Удалить", width=100, fg_color=("#f44336", "#d32f2f"), hover_color=("#da190b", "#b71c1c"), command=lambda: self.delete_server(server_data, dialog)).pack(side="left")

    def show_password(self, password):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Пароль администратора")
        dialog.geometry("400x150")
        dialog.transient(self)
        dialog.grab_set()
        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=30)
        ctk.CTkLabel(content, text="Пароль администратора FastPanel:", font=ctk.CTkFont(size=12)).pack(pady=(0, 10))
        password_frame = ctk.CTkFrame(content, fg_color=("#f5f5f5", "#1a1a1a"), corner_radius=5)
        password_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(password_frame, text=password, font=ctk.CTkFont(family="Courier", size=14, weight="bold")).pack(padx=10, pady=10)
        ctk.CTkButton(content, text="Закрыть", width=100, command=dialog.destroy).pack(pady=(10, 0))

    def add_or_update_server(self, server_type, server_data=None):
        is_editing = server_data is not None
        
        if server_type == 'new':
            payload = {
                "name": self.server_name_entry.get(),
                "ip": self.server_ip_entry.get(),
                "ssh_user": self.server_user_entry.get() or "root",
                "password": self.server_password_entry.get(),
                "expiration_date": self.server_expiration_entry.get()
            }
            if not payload["name"] or not payload["ip"]:
                self.show_error("Имя и IP обязательны")
                return
        else: # existing
            payload = {
                "name": self.existing_server_name_entry.get(),
                "admin_url": self.server_url_entry.get(),
                "admin_password": self.fastuser_password_entry.get(),
                "expiration_date": self.existing_server_expiration_entry.get()
            }
            if not payload["admin_url"] or not payload["admin_password"]:
                self.show_error("URL и пароль обязательны")
                return
            try:
                payload["ip"] = payload["admin_url"].split("://")[1].split(":")[0]
            except:
                self.show_error("Неверный формат URL")
                return
            if not payload["name"]: payload["name"] = payload["ip"]

        if is_editing:
            for i, s in enumerate(self.servers):
                if s['id'] == server_data['id']:
                    self.servers[i].update(payload)
                    break
            self.log_action(f"Сервер '{payload['name']}' обновлен")
            self.show_success(f"Сервер {payload['name']} обновлен")
        else:
            payload.update({
                "id": str(uuid.uuid4())[:8],
                "fastpanel_installed": server_type == "existing",
                "created_at": datetime.now().isoformat(),
            })
            self.servers.append(payload)
            self.log_action(f"Добавлен новый сервер: '{payload['name']}'")
            self.show_success(f"Сервер {payload['name']} добавлен")

        self.save_servers()
        self.show_servers_tab()

    def delete_server(self, server_data, dialog):
        self.servers = [s for s in self.servers if s["id"] != server_data["id"]]
        self.save_servers()
        dialog.destroy()
        self.log_action(f"Сервер '{server_data['name']}' удален", level="WARNING")
        self.show_success(f"Сервер {server_data['name']} удален")
        self.show_servers_tab()

    def delete_domain_from_server(self, domain, server_data):
        self.domains = [d for d in self.domains if not (d['domain'] == domain['domain'] and d['server_ip'] == domain['server_ip'])]
        self.save_domains()
        self.log_action(f"Домен {domain['domain']} удален с сервера {server_data['name']}", level="WARNING")
        self.show_success(f"Домен {domain['domain']} удален")
        self.show_server_management(server_data)

    def start_installation(self, server_data, password, log_widget, progress_widget):
        self.log_action(f"Запуск установки FastPanel на сервер '{server_data['name']}'")
        log_widget.insert("end", "🚀 Начинаем установку FastPanel...\n")
        progress_widget.set(0.1)
        # ... (здесь будет реальный код установки)

    def _complete_installation(self, server_data, log_widget, progress_widget):
        self.log_action(f"Установка FastPanel на сервер '{server_data['name']}' завершена", level="SUCCESS")
        log_widget.insert("end", "\n✅ FastPanel успешно установлен!\n")
        # ... (здесь будет реальный код после установки)

    def load_servers(self):
        try:
            with open("data/servers.json", 'r', encoding='utf-8') as f: self.servers = json.load(f)
            self.log_action(f"Загружено {len(self.servers)} серверов")
        except (FileNotFoundError, json.JSONDecodeError): self.servers = []

    def save_servers(self):
        os.makedirs("data", exist_ok=True)
        with open("data/servers.json", 'w', encoding='utf-8') as f: json.dump(self.servers, f, indent=2, ensure_ascii=False)

    def load_domains(self):
        try:
            with open("data/domains.json", 'r', encoding='utf-8') as f: self.domains = json.load(f)
            self.log_action(f"Загружено {len(self.domains)} доменов")
        except (FileNotFoundError, json.JSONDecodeError): self.domains = []

    def save_domains(self):
        os.makedirs("data", exist_ok=True)
        with open("data/domains.json", 'w', encoding='utf-8') as f: json.dump(self.domains, f, indent=2, ensure_ascii=False)

    def refresh_data(self):
        self.load_servers()
        self.load_domains()
        if self.current_tab == "servers": self.show_servers_tab()
        elif self.current_tab == "domain": self.show_domain_tab()
        self.log_action("Данные обновлены")
        self.show_success("Данные обновлены")
        
    def log_action(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs.append(f"[{timestamp}] {level}: {message}")

    def show_success(self, message):
        self.status_label.configure(text=f"✅ {message}", text_color=("#4caf50", "#4caf50"))
        self.after(3000, lambda: self.status_label.configure(text="● Готов к работе", text_color=("#4caf50", "#4caf50")))

    def show_error(self, message):
        self.status_label.configure(text=f"❌ {message}", text_color=("#f44336", "#f44336"))
        self.log_action(message, level="ERROR")
        self.after(3000, lambda: self.status_label.configure(text="● Готов к работе", text_color=("#4caf50", "#4caf50")))

if __name__ == "__main__":
    app = FastPanelApp()
    app.mainloop()
