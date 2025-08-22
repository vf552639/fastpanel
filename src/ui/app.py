"""
FastPanel Automation GUI
Современный интерфейс для управления серверами и FastPanel
"""
import customtkinter as ctk
from typing import Optional, Dict, List
import json
from pathlib import Path
from datetime import datetime, timedelta
import threading
from PIL import Image
import os
import sys
import uuid
import webbrowser
import ipaddress
from src.services.fastpanel import FastPanelService
from src.core.ssh_manager import SSHManager
from functools import partial
from src.services.cloudflare_service import CloudflareService
from src.services.namecheap_service import NamecheapService
from src.core.database_manager import DatabaseManager
import time


# Настройка внешнего вида
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class InstructionWindow(ctk.CTkToplevel):
    """Окно для отображения инструкций."""
    def __init__(self, parent, title, instruction_text):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x400")
        self.transient(parent)
        self.grab_set()

        self.textbox = ctk.CTkTextbox(self, wrap="word", font=("Arial", 14))
        self.textbox.pack(padx=20, pady=20, fill="both", expand=True)
        self.textbox.insert("1.0", instruction_text)
        self.textbox.configure(state="disabled")

        close_button = ctk.CTkButton(self, text="Закрыть", command=self.destroy)
        close_button.pack(pady=10)


class AutomationProgressWindow(ctk.CTkToplevel):
    """Окно для отображения прогресса и логов автоматизации."""
    def __init__(self, parent, server_name, total_domains):
        super().__init__(parent)
        self.title(f"Автоматизация: {server_name}")
        self.geometry("800x600")
        self.transient(parent)

        self.progress = 0
        self.total = total_domains

        self.progress_label = ctk.CTkLabel(self, text="Запуск...")
        self.progress_label.pack(pady=10, padx=20, fill="x")

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10, padx=20, fill="x")

        self.log_textbox = ctk.CTkTextbox(self, wrap="word", state="disabled", font=("Courier", 12))
        self.log_textbox.pack(pady=10, padx=20, fill="both", expand=True)

    def add_log(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def increment_progress(self):
        self.progress += 1
        progress_value = self.progress / self.total if self.total > 0 else 0
        self.progress_bar.set(progress_value)
        self.progress_label.configure(text=f"Обработано {self.progress} из {self.total} доменов")


class ServerCard(ctk.CTkFrame):
    """Карточка сервера для отображения в списке"""

    def __init__(self, parent, server_data: dict, on_click=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.server_data = server_data
        self.on_click = on_click
        self.app = self.winfo_toplevel()

        self.configure(
            corner_radius=10,
            fg_color=("#ffffff", "#2b2b2b"),
            border_width=1,
            border_color=("#e0e0e0", "#404040")
        )

        self._create_widgets()
        self.check_installation_status()

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

        if self.server_data.get("fastpanel_installed"):
            status_badge = ctk.CTkLabel(info_frame, text="✅ FastPanel установлен", font=ctk.CTkFont(size=11), text_color=("#4caf50", "#2e7d32"), anchor="w")
            status_badge.pack(fill="x", pady=(2,0))
        else:
            status_badge = ctk.CTkLabel(info_frame, text="⏳ Не установлен", font=ctk.CTkFont(size=11), text_color=("#ff9800", "#f57c00"), anchor="w")
            status_badge.pack(fill="x", pady=(2,0))

        automation_btn = ctk.CTkButton(top_frame, text="▶️ Запустить автоматизацию", command=lambda: self._on_start_automation())
        automation_btn.pack(side="right", padx=(10,0))

        app = self.winfo_toplevel()
        server_has_domains = any(d.get("server_id") == self.server_data.get("id") for d in app.domains)
        if not server_has_domains or not self.server_data.get("fastpanel_installed"):
            automation_btn.configure(state="disabled")


        separator = ctk.CTkFrame(main_frame, height=1, fg_color=("#e0e0e0", "#404040"))
        separator.pack(fill="x", pady=8)

        bottom_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        bottom_frame.pack(fill="x")

        # --- WIDGETS FOR INSTALLATION ---
        self.install_progress = ctk.CTkProgressBar(bottom_frame)
        self.install_progress.set(0)

        self.log_button = ctk.CTkButton(bottom_frame, text="Посмотреть лог", width=120, height=28, font=ctk.CTkFont(size=12), command=self._on_show_log)

        # --- REGULAR WIDGETS ---
        if self.server_data.get("fastpanel_installed"):
            self.manage_btn = ctk.CTkButton(bottom_frame, text="Управление", width=100, height=28, font=ctk.CTkFont(size=12), command=lambda: self._on_manage())
            self.manage_btn.pack(side="left", padx=(0, 5))
            self.panel_btn = ctk.CTkButton(bottom_frame, text="Открыть панель", width=100, height=28, font=ctk.CTkFont(size=12), fg_color=("#4caf50", "#2e7d32"), hover_color=("#45a049", "#1b5e20"), command=lambda: self._open_panel())
            self.panel_btn.pack(side="left", padx=5)
        else:
            self.install_btn = ctk.CTkButton(bottom_frame, text="Установить FastPanel", width=150, height=28, font=ctk.CTkFont(size=12), fg_color=("#2196f3", "#1976d2"), hover_color=("#1976d2", "#1565c0"), command=lambda: self._on_install())
            self.install_btn.pack(side="left")

        self.delete_btn = ctk.CTkButton(bottom_frame, text="🗑️", width=30, height=28, fg_color=("#f44336", "#d32f2f"), hover_color=("#da190b", "#b71c1c"), command=lambda: self._on_delete())
        self.delete_btn.pack(side="right")

        self.edit_btn = ctk.CTkButton(bottom_frame, text="✏️", width=30, height=28, command=lambda: self._on_edit())
        self.edit_btn.pack(side="right", padx=5)

    def set_install_mode(self, installing=True):
        if installing:
            self.install_btn.pack_forget()
            if hasattr(self, 'manage_btn'): self.manage_btn.pack_forget()
            if hasattr(self, 'panel_btn'): self.panel_btn.pack_forget()

            self.install_progress.pack(side="left", fill="x", expand=True, padx=(0,10))
            self.log_button.pack(side="left")
        # No 'else' needed as the whole UI will be redrawn

    def check_installation_status(self):
        server_id = self.server_data.get("id")
        if server_id in self.app.installation_states and self.app.installation_states[server_id].get("installing"):
            self.set_install_mode(True)

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

    def _on_start_automation(self):
        if self.on_click: self.on_click("start_automation", self.server_data)

    def _on_show_log(self):
        if self.on_click: self.on_click("show_log", self.server_data)

class FastPanelApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FastPanel Automation")
        self.geometry("1200x700")
        self.minsize(1000, 600)
        self.center_window()

        self.db = DatabaseManager()

        self.servers = []
        self.domains = []
        self.logs = []
        self.current_tab = "servers"
        self.installation_states = {}
        self.domain_widgets = {}
        self.selected_domains = set()
        self.server_metrics = {}
        self.server_statuses = {}

        self.app_settings = {}
        self.credentials = {}

        self.load_data_from_db()

        self.log_action("Приложение запущено")
        self._create_widgets()
        self.after(100, self._update_server_list)

        if sys.platform == "darwin" and os.path.exists("assets/icon.icns"):
            self.iconbitmap("assets/icon.icns")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        ## ИЗМЕНЕНО: Исправление вставки на macOS
        # Используем виртуальное событие <<Paste>> которое не зависит от раскладки
        self.bind_class("CTkEntry", "<<Paste>>", self.handle_paste)
        self.bind_class("CTkTextbox", "<<Paste>>", self.handle_paste)

        self.check_server_renewals()
        self.start_monitoring()

    ## ИЗМЕНЕНО: Обработчик вставки
    def handle_paste(self, event):
        """Обработка вставки из буфера обмена для всех виджетов."""
        try:
            # event.widget - это виджет, который получил событие
            widget = event.widget
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkTextbox)):
                widget.insert("insert", self.clipboard_get())
        except Exception as e:
            self.log_action(f"Ошибка вставки: {e}", "WARNING")
        # Возвращаем "break", чтобы предотвратить дальнейшую обработку события
        return "break"

    def on_closing(self):
        self.db.close()
        self.destroy()

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

        self.nav_buttons = {}
        for icon, text, command in nav_buttons:
            btn = ctk.CTkButton(self.sidebar, text=f"{icon}  {text}", font=ctk.CTkFont(size=14), height=40, fg_color="transparent", text_color=("#000000", "#ffffff"), hover_color=("#e0e0e0", "#404040"), anchor="w", command=command)
            btn.pack(fill="x", padx=15, pady=2)
            self.nav_buttons[text] = btn


        info_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        info_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkLabel(info_frame, text="Version 1.3.0", font=ctk.CTkFont(size=10), text_color=("#999999", "#666666")).pack()
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
        if not hasattr(self, 'scrollable_servers'): return
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
                card = ServerCard(self.scrollable_servers, server, on_click=self.handle_server_action)
                card.pack(fill="x", pady=5)
                server_id = server.get("id")
                if server_id and server_id in self.installation_states:
                    self.installation_states[server_id]['card'] = card

    def add_or_update_server(self, server_type, server_data=None):
        is_editing = server_data is not None

        if server_type == 'new':
            ip = self.server_ip_entry.get()
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                self.show_error("Неверный формат IP адреса")
                return

            payload = {
                "name": self.server_name_entry.get(),
                "ip": ip,
                "ssh_user": self.server_user_entry.get() or "root",
                "password": self.server_password_entry.get(),
                "created_at": datetime.now().strftime("%Y-%m-%d"),
                "hosting_period_days": int(self.hosting_period_entry.get() or 30)
            }
            if not payload["name"] or not payload["ip"]:
                self.show_error("Имя и IP обязательны")
                return
        else: # existing
            payload = {
                "name": self.existing_server_name_entry.get(),
                "admin_url": self.server_url_entry.get(),
                "admin_password": self.fastuser_password_entry.get(),
                 "hosting_period_days": int(self.existing_hosting_period_entry.get() or 30)
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
            self.db.update_server(server_data['id'], payload)
            self.log_action(f"Сервер '{payload['name']}' обновлен")
            self.show_success(f"Сервер {payload['name']} обновлен")
        else:
            payload.update({
                "id": str(uuid.uuid4())[:8],
                "fastpanel_installed": server_type == "existing",
            })
            if self.db.add_server(payload):
                self.log_action(f"Добавлен новый сервер: '{payload['name']}'")
                self.show_success(f"Сервер {payload['name']} добавлен")
            else:
                self.show_error(f"Сервер с IP {payload['ip']} уже существует!")
                return

        self.refresh_data()
        self.show_servers_tab()

    def delete_server(self, server_data, dialog):
        server_id = server_data["id"]
        self.db.delete_server(server_id)
        self.servers = [s for s in self.servers if s["id"] != server_id]
        dialog.destroy()
        self.log_action(f"Сервер '{server_data['name']}' удален", level="WARNING")
        self.show_success(f"Сервер {server_data['name']} удален")
        self._update_server_list()

    def delete_domain(self, domain_info):
        self.db.delete_domain(domain_info['domain_name'])
        self.log_action(f"Домен {domain_info['domain_name']} удален", level="WARNING")
        self.show_success(f"Домен {domain_info['domain_name']} удален")
        self.refresh_data()
        self.show_domain_tab()

    def delete_domain_from_server(self, domain, server_data):
        confirm_dialog = ctk.CTkToplevel(self)
        confirm_dialog.title("Подтверждение")
        confirm_dialog.geometry("350x150")
        confirm_dialog.transient(self)
        confirm_dialog.grab_set()

        ctk.CTkLabel(confirm_dialog, text=f"Удалить сайт {domain['domain_name']}?", font=ctk.CTkFont(size=14)).pack(pady=20)
        
        btn_frame = ctk.CTkFrame(confirm_dialog, fg_color="transparent")
        btn_frame.pack(pady=10)

        def do_delete():
            confirm_dialog.destroy()
            self.db.delete_domain(domain['domain_name'])
            self.log_action(f"Домен {domain['domain_name']} удален с сервера {server_data['name']}", level="WARNING")
            self.show_success(f"Домен {domain['domain_name']} удален")
            self.refresh_data()
            self.after(100, lambda: self.show_server_management(server_data))

        ctk.CTkButton(btn_frame, text="Отмена", command=confirm_dialog.destroy).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Удалить", fg_color="red", command=do_delete).pack(side="left", padx=10)


    def start_installation(self, server_data):
        server_id = server_data.get("id")
        if not server_id or (server_id in self.installation_states and self.installation_states[server_id].get("installing")):
            self.show_error("Установка уже запущена")
            return

        password = server_data.get("password")
        if not password:
            self.show_error("Пароль SSH не найден для этого сервера.")
            return

        self.server_statuses[server_id] = "installing"
        self.log_action(f"Запуск установки FastPanel на сервер '{server_data['name']}'")
        self.installation_states[server_id] = {"installing": True, "log": [], "progress": 0.0, "card": None, "log_window": None}
        self._update_server_list()
        install_thread = threading.Thread(target=self._run_installation_in_thread, args=(server_data, password, server_id), daemon=True)
        install_thread.start()

    def _run_installation_in_thread(self, server_data, password, server_id):
        def update_ui_callback(message, progress):
            def _update():
                state = self.installation_states.get(server_id)
                if not state: return
                state["log"].append(message)
                state["progress"] = progress
                if state.get("card"): state["card"].install_progress.set(progress)
                if state.get("log_window"):
                    state["log_window"].log_text.insert("end", message + "\n")
                    state["log_window"].log_text.see("end")
            self.after(0, _update)
        service = FastPanelService()
        result = service.install(host=server_data['ip'], username=server_data.get('ssh_user', 'root'), password=password, callback=update_ui_callback)
        self.after(0, self._on_installation_finished, result, server_data, server_id)

    def _on_installation_finished(self, result, server_data, server_id):
        self.server_statuses[server_id] = "idle"
        if server_id in self.installation_states: self.installation_states[server_id]["installing"] = False
        if result['success']:
            self.show_success(f"FastPanel на '{server_data['name']}' успешно установлен!")
            self.log_action(f"Установка FastPanel на '{server_data['name']}' завершена успешно", level="SUCCESS")
            update_data = {"fastpanel_installed": True, "admin_url": result['admin_url'], "admin_password": result['admin_password'], "install_date": result['install_time']}
            self.db.update_server(server_id, update_data)
            for i, s in enumerate(self.servers):
                if s['id'] == server_id: self.servers[i].update(update_data); break
        else:
            error_message = result.get('error', 'Неизвестная ошибка')
            self.show_error("Ошибка установки!")
            self.log_action(f"Ошибка установки на '{server_data['name']}': {error_message}", level="ERROR")
        self._update_server_list()

    def refresh_data(self):
        self.load_data_from_db()
        self.check_server_renewals()
        if self.current_tab == "servers": self.show_servers_tab()
        elif self.current_tab == "domain": self.show_domain_tab()
        elif self.current_tab == "monitoring": self.show_monitoring_tab()
        self.log_action("Данные обновлены")
        self.show_success("Данные обновлены")

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
        if server_type == "new": self.create_new_server_form(self.fields_frame, server_data)
        else: self.create_existing_server_form(self.fields_frame, server_data)
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
        ctk.CTkLabel(parent, text="Срок аренды (дней)", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.hosting_period_entry = ctk.CTkEntry(parent, width=400, height=40)
        self.hosting_period_entry.pack(pady=(0, 15), fill="x", expand=True)
        self.hosting_period_entry.insert(0, str(data.get("hosting_period_days", 30)) if data else "30")

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
        ctk.CTkLabel(parent, text="Срок аренды (дней)", font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", pady=(0, 5))
        self.existing_hosting_period_entry = ctk.CTkEntry(parent, width=400, height=40)
        self.existing_hosting_period_entry.pack(pady=(0, 15), fill="x", expand=True)
        self.existing_hosting_period_entry.insert(0, str(data.get("hosting_period_days", 30)) if data else "30")

    def show_domain_tab(self):
        self.clear_tab_container()
        self.page_title.configure(text="Управление доменами")
        self.current_tab = "domain"
        self.domain_widgets.clear()
        self.selected_domains.clear()
        
        action_panel = ctk.CTkFrame(self.tab_container, fg_color="transparent")
        action_panel.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(action_panel, text="➕ Добавить домен(-ы)", command=self.show_add_domain_dialog).pack(side="left")
        self.bind_cf_button = ctk.CTkButton(action_panel, text="🔗 Привязать к Cloudflare", state="disabled", command=self.start_cloudflare_binding)
        self.bind_cf_button.pack(side="left", padx=10)
        self.delete_domain_button = ctk.CTkButton(action_panel, text="🗑️ Удалить выбранные", state="disabled", fg_color=("#f44336", "#d32f2f"), hover_color=("#da190b", "#b71c1c"), command=self.confirm_delete_selected_domains)
        self.delete_domain_button.pack(side="left", padx=10)
        ctk.CTkButton(action_panel, text="✏️ Редактировать колонки", command=self.show_edit_columns_dialog).pack(side="left", padx=10)
        
        self.domain_header = ctk.CTkFrame(self.tab_container, fg_color=("#e0e0e0", "#333333"), height=40)
        self.domain_header.pack(fill="x", pady=5)
        self.update_domain_columns()
        
        domain_list_frame = ctk.CTkScrollableFrame(self.tab_container, fg_color="transparent")
        domain_list_frame.pack(fill="both", expand=True)
        
        if not self.domains:
            ctk.CTkLabel(domain_list_frame, text="Нет добавленных доменов").pack(pady=20)
        else:
            for domain_info in self.domains: 
                self.add_domain_row(domain_list_frame, domain_info)

    def confirm_delete_selected_domains(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Подтверждение удаления")
        dialog.geometry("400x200")
        dialog.transient(self)
        dialog.grab_set()
        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=30)
        ctk.CTkLabel(content, text="⚠️ Удаление доменов", font=ctk.CTkFont(size=18, weight="bold"), text_color=("#f44336", "#f44336")).pack(pady=(0, 20))
        ctk.CTkLabel(content, text=f"Вы уверены, что хотите удалить {len(self.selected_domains)} домен(ов)?", font=ctk.CTkFont(size=12)).pack(pady=(0, 30))
        buttons_frame = ctk.CTkFrame(content, fg_color="transparent")
        buttons_frame.pack()
        ctk.CTkButton(buttons_frame, text="Отмена", width=100, fg_color="transparent", border_width=1, text_color=("#000000", "#ffffff"), border_color=("#e0e0e0", "#404040"), command=dialog.destroy).pack(side="left", padx=(0, 10))
        ctk.CTkButton(buttons_frame, text="Удалить", width=100, fg_color=("#f44336", "#d32f2f"), hover_color=("#da190b", "#b71c1c"), command=lambda: self.delete_selected_domains(dialog)).pack(side="left")

    def delete_selected_domains(self, dialog):
        for domain_name in list(self.selected_domains):
            self.db.delete_domain(domain_name)
            self.log_action(f"Домен {domain_name} удален", level="WARNING")
        self.refresh_data()
        self.show_domain_tab()
        dialog.destroy()
        self.show_success(f"Выбранные домены удалены")

    def update_domain_columns(self):
        for widget in self.domain_header.winfo_children(): 
            widget.destroy()
        
        # Обновленная конфигурация колонок с правильными весами и выравниванием
        self.all_columns = {
            "Домен": {"weight": 3, "min": 200, "visible": True, "anchor": "center"},
            "Сервер": {"weight": 2, "min": 180, "visible": True, "anchor": "center"},
            "Статус Cloudflare": {"weight": 2, "min": 160, "visible": True, "anchor": "center"},
            "NS-серверы Cloudflare": {"weight": 3, "min": 250, "visible": self.app_settings.get('column_visibility', {}).get("NS-серверы Cloudflare", True), "anchor": "center"},
            "FTP": {"weight": 1, "min": 80, "visible": True, "anchor": "center"},
            "SSL": {"weight": 1, "min": 120, "visible": True, "anchor": "center"},
            "Действия": {"weight": 1, "min": 100, "visible": True, "anchor": "center"}  # Новая колонка для кнопок
        }
        
        # Чекбокс колонка
        self.domain_header.grid_columnconfigure(0, weight=0, minsize=40)
        
        col_index = 1
        for name, props in self.all_columns.items():
            if props["visible"]:
                self.domain_header.grid_columnconfigure(col_index, weight=props["weight"], minsize=props["min"])
                label = ctk.CTkLabel(self.domain_header, text=name, anchor=props["anchor"], font=ctk.CTkFont(size=12, weight="bold"))
                label.grid(row=0, column=col_index, padx=5, pady=5, sticky="ew")
                col_index += 1

    def show_edit_columns_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Редактировать колонки")
        dialog.geometry("300x250")
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Выберите видимые колонки", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=15)
        togglable_columns = ["NS-серверы Cloudflare"]
        for col_name in togglable_columns:
            var = ctk.BooleanVar(value=self.app_settings.get('column_visibility', {}).get(col_name, True))
            cb = ctk.CTkCheckBox(dialog, text=col_name, variable=var, command=lambda name=col_name, v=var: self.toggle_column_visibility(name, v))
            cb.pack(pady=5, padx=20, anchor="w")
        ctk.CTkButton(dialog, text="Закрыть", command=dialog.destroy).pack(pady=20)

    def toggle_column_visibility(self, column_name, var):
        is_visible = var.get()
        if 'column_visibility' not in self.app_settings: self.app_settings['column_visibility'] = {}
        self.app_settings['column_visibility'][column_name] = is_visible
        self.db.save_setting('column_visibility', self.app_settings['column_visibility'])
        self.show_domain_tab()

    def add_domain_row(self, parent, domain_info):
        domain = domain_info["domain_name"]
        
        # Основной фрейм для строки
        domain_frame = ctk.CTkFrame(parent, fg_color=("#ffffff", "#2b2b2b"), corner_radius=5, border_width=1, border_color=("#e0e0e0", "#404040"))
        domain_frame.pack(fill="x", pady=2)
        
        # Настройка колонок для строки (должна соответствовать заголовку)
        domain_frame.grid_columnconfigure(0, weight=0, minsize=40)  # Чекбокс
        
        col_index = 1
        visible_columns = {name: props for name, props in self.all_columns.items() if props['visible']}
        for name, props in visible_columns.items():
            domain_frame.grid_columnconfigure(col_index, weight=props['weight'], minsize=props['min'])
            col_index += 1
        
        # Чекбокс
        var = ctk.BooleanVar()
        checkbox = ctk.CTkCheckBox(domain_frame, text="", variable=var, width=30, command=lambda d=domain: self.toggle_domain_selection(d, var))
        checkbox.grid(row=0, column=0, padx=5, pady=8, sticky="w")
        
        current_col = 1
        
        # Домен (центрированный)
        domain_label = ctk.CTkLabel(domain_frame, text=domain, font=ctk.CTkFont(size=13), anchor="center")
        domain_label.grid(row=0, column=current_col, padx=5, pady=8, sticky="ew")
        current_col += 1
        
        # Сервер
        server_ips = ["(Не выбран)"] + [s['ip'] for s in self.servers if s.get('ip')]
        server_ip_value = "(Не выбран)"
        if domain_info.get("server_id"):
            server = next((s for s in self.servers if s['id'] == domain_info.get("server_id")), None)
            if server: 
                server_ip_value = server['ip']
        
        server_var = ctk.StringVar(value=server_ip_value)
        server_menu = ctk.CTkOptionMenu(
            domain_frame, 
            values=server_ips, 
            variable=server_var, 
            width=150,
            anchor="center",
            command=lambda ip, d=domain: self.update_domain_server(d, ip)
        )
        server_menu.grid(row=0, column=current_col, padx=5, pady=8, sticky="ew")
        current_col += 1
        
        # Статус Cloudflare
        status_colors = {
            "none": ("#666666", "#aaaaaa"),
            "pending": ("#ff9800", "#f57c00"),
            "active": ("#4caf50", "#2e7d32"),
            "error": ("#f44336", "#d32f2f")
        }
        status_text = {
            "none": "⚪ Не привязан",
            "pending": "🟡 В процессе...",
            "active": "🟢 Активен",
            "error": "🔴 Ошибка"
        }
        status = domain_info.get("cloudflare_status", "none")
        status_label = ctk.CTkLabel(
            domain_frame,
            text=status_text.get(status),
            text_color=status_colors.get(status),
            anchor="center",
            font=ctk.CTkFont(size=12)
        )
        status_label.grid(row=0, column=current_col, padx=5, pady=8, sticky="ew")
        current_col += 1
        
        # NS-серверы Cloudflare (если видимы)
        if self.all_columns["NS-серверы Cloudflare"]["visible"]:
            ns_servers = domain_info.get("cloudflare_ns", "")
            ns_label = ctk.CTkLabel(
                domain_frame,
                text=ns_servers,
                anchor="center",
                wraplength=250,
                justify="center",
                font=ctk.CTkFont(size=11)
            )
            ns_label.grid(row=0, column=current_col, padx=5, pady=8, sticky="ew")
            current_col += 1
        
        # FTP кнопка
        ftp_button = ctk.CTkButton(
            domain_frame,
            text="🖥️ FTP",
            width=70,
            height=28,
            font=ctk.CTkFont(size=11),
            command=lambda d=domain_info: self.show_ftp_credentials_dialog(d)
        )
        ftp_button.grid(row=0, column=current_col, padx=5, pady=8)
        if not domain_info.get("ftp_user"):
            ftp_button.configure(state="disabled")
        current_col += 1
        
        # SSL кнопка
        ssl_status = domain_info.get("ssl_status", "none")
        ssl_button = ctk.CTkButton(domain_frame, height=28, font=ctk.CTkFont(size=11))
        
        if ssl_status == "active":
            ssl_button.configure(text="✅ Активен", fg_color="green", width=100, command=lambda d=domain_info: self.start_ssl_issuance(d))
        elif ssl_status == "pending":
            ssl_button.configure(text="⏳ Выпускается", state="disabled", width=100)
        elif ssl_status == "error":
            ssl_button.configure(text="❌ Ошибка", fg_color="red", width=100, command=lambda d=domain_info: self.start_ssl_issuance(d))
        else:
            ssl_button.configure(text="Выпустить", width=100, command=lambda d=domain_info: self.start_ssl_issuance(d))
        
        ssl_button.grid(row=0, column=current_col, padx=5, pady=8)
        if not domain_info.get("server_id"):
            ssl_button.configure(state="disabled")
        current_col += 1
        
        # Действия (редактирование и удаление в одной колонке)
        actions_frame = ctk.CTkFrame(domain_frame, fg_color="transparent")
        actions_frame.grid(row=0, column=current_col, padx=5, pady=8, sticky="ew")
        
        # Центрируем кнопки в колонке действий
        actions_frame.grid_columnconfigure(0, weight=1)
        actions_frame.grid_columnconfigure(1, weight=0)
        actions_frame.grid_columnconfigure(2, weight=0)
        actions_frame.grid_columnconfigure(3, weight=1)
        
        edit_button = ctk.CTkButton(
            actions_frame,
            text="✏️",
            width=30,
            height=28,
            font=ctk.CTkFont(size=12),
            command=lambda d=domain_info: self.show_edit_domain_dialog(d)
        )
        edit_button.grid(row=0, column=1, padx=2)
        
        delete_button = ctk.CTkButton(
            actions_frame,
            text="🗑️",
            width=30,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color=("#f44336", "#d32f2f"),
            hover_color=("#da190b", "#b71c1c"),
            command=lambda d=domain_info: self.delete_domain(d)
        )
        delete_button.grid(row=0, column=2, padx=2)
        
        # Сохраняем ссылки на виджеты для обновления
        self.domain_widgets[domain] = {
            "frame": domain_frame,
            "status_label": status_label,
            "ssl_button": ssl_button
        }
        if self.all_columns["NS-серверы Cloudflare"]["visible"]:
            self.domain_widgets[domain]["ns_label"] = ns_label
            
    def show_edit_domain_dialog(self, domain_info):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Редактировать: {domain_info['domain_name']}")
        dialog.geometry("600x650") # Increased height for new fields
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=f"Редактирование {domain_info['domain_name']}", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=20)
        
        scroll_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)

        def create_row(parent, label_text):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=8)
            ctk.CTkLabel(row, text=label_text, width=180, anchor="w").pack(side="left")
            return row

        # Server
        server_row = create_row(scroll_frame, "Сервер:")
        server_ips = ["(Не выбран)"] + [s['ip'] for s in self.servers if s.get('ip')]
        server_ip_value = "(Не выбран)"
        if domain_info.get("server_id"):
            server = next((s for s in self.servers if s['id'] == domain_info.get("server_id")), None)
            if server: server_ip_value = server['ip']
        server_var = ctk.StringVar(value=server_ip_value)
        server_menu = ctk.CTkOptionMenu(server_row, values=server_ips, variable=server_var, width=250)
        server_menu.pack(side="left")
        
        # Purchase Date
        purchase_date_row = create_row(scroll_frame, "Дата покупки (ГГГГ-ММ-ДД):")
        purchase_date_entry = ctk.CTkEntry(purchase_date_row, width=250)
        # FIX: Ensure value is a string to prevent TclError
        purchase_date_entry.insert(0, str(domain_info.get("purchase_date") or ""))
        purchase_date_entry.pack(side="left")
        
        # Registrar
        registrar_row = create_row(scroll_frame, "Регистратор:")
        registrar_entry = ctk.CTkEntry(registrar_row, width=250)
        registrar_entry.insert(0, str(domain_info.get("registrar") or ""))
        registrar_entry.pack(side="left")
        
        # WordPress
        wp_row = create_row(scroll_frame, "WordPress:")
        wp_installed_var = ctk.BooleanVar(value=domain_info.get("wordpress_installed", False))
        wp_checkbox = ctk.CTkCheckBox(wp_row, text="Установить WordPress (заглушка)", variable=wp_installed_var)
        wp_checkbox.pack(side="left")

        # Backup
        backup_row = create_row(scroll_frame, "Резервное копирование:")
        backup_enabled_var = ctk.BooleanVar(value=domain_info.get("backup_enabled", False))
        backup_checkbox = ctk.CTkCheckBox(backup_row, text="Включить", variable=backup_enabled_var)
        backup_checkbox.pack(side="left", padx=(0, 10))

        backup_freq_var = ctk.StringVar(value=domain_info.get("backup_frequency", "еженедельно"))
        backup_freq_menu = ctk.CTkOptionMenu(backup_row, values=["ежедневно", "еженедельно", "ежемесячно"], variable=backup_freq_var)
        backup_freq_menu.pack(side="left")

        ctk.CTkFrame(scroll_frame, height=1, fg_color=("#e0e0e0", "#404040")).pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(scroll_frame, text="Информационные поля", font=ctk.CTkFont(size=14, weight="bold")).pack(padx=20, anchor="w")

        # NS Servers Info
        ns_row = create_row(scroll_frame, "NS-серверы:")
        ns_info_label = ctk.CTkLabel(ns_row, text=str(domain_info.get("cloudflare_ns") or "Не заданы"), anchor="w")
        ns_info_label.pack(side="left")

        # FTP Info
        ftp_user_row = create_row(scroll_frame, "FTP Логин:")
        ftp_user_label = ctk.CTkLabel(ftp_user_row, text=str(domain_info.get("ftp_user") or "Нет"), anchor="w")
        ftp_user_label.pack(side="left")
        
        ftp_pass_row = create_row(scroll_frame, "FTP Пароль:")
        ftp_pass_label = ctk.CTkLabel(ftp_pass_row, text=str(domain_info.get("ftp_password") or "Нет"), anchor="w")
        ftp_pass_label.pack(side="left")
        
        # Notes
        notes_row = create_row(scroll_frame, "Комментарий:")
        notes_text = ctk.CTkTextbox(scroll_frame, height=100)
        notes_text.insert("1.0", domain_info.get("notes", ""))
        notes_text.pack(fill="x", padx=20, pady=5)
        
        def save_changes():
            selected_server = next((s for s in self.servers if s['ip'] == server_var.get()), None)
            updated_data = {
                "server_id": selected_server['id'] if selected_server else None,
                "purchase_date": purchase_date_entry.get(),
                "registrar": registrar_entry.get(),
                "wordpress_installed": wp_installed_var.get(),
                "backup_enabled": backup_enabled_var.get(),
                "backup_frequency": backup_freq_var.get(),
                "notes": notes_text.get("1.0", "end-1c"),
            }
            # Auto-calculate renewal date if purchase date is provided
            try:
                purchase_dt = datetime.strptime(updated_data["purchase_date"], "%Y-%m-%d")
                updated_data["renewal_date"] = (purchase_dt + timedelta(days=365)).strftime("%Y-%m-%d")
            except ValueError:
                updated_data["renewal_date"] = ""

            self.db.update_domain(domain_info['domain_name'], updated_data)
            self.refresh_data()
            dialog.destroy()
        
        ctk.CTkButton(dialog, text="Сохранить", command=save_changes).pack(pady=20)


    def show_ftp_credentials_dialog(self, domain_info):
        server_ip = "N/A"
        if domain_info.get("server_id"):
            server = next((s for s in self.servers if s['id'] == domain_info.get("server_id")), None)
            if server: server_ip = server['ip']
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"FTP: {domain_info['domain_name']}")
        dialog.geometry("450x250")
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=f"FTP доступы для {domain_info['domain_name']}", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 15))
        def copy_to_clipboard(text_to_copy):
            self.clipboard_clear()
            self.clipboard_append(text_to_copy)
            self.show_success(f"Скопировано!")
        def create_credential_row(parent, label_text, value_text):
            row_frame = ctk.CTkFrame(parent, fg_color="transparent")
            row_frame.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(row_frame, text=label_text, width=80, anchor="w").pack(side="left")
            value_entry = ctk.CTkEntry(row_frame)
            value_entry.insert(0, value_text)
            value_entry.configure(state="readonly")
            value_entry.pack(side="left", fill="x", expand=True, padx=(10, 5))
            ctk.CTkButton(row_frame, text="📋", width=30, command=lambda: copy_to_clipboard(value_text)).pack(side="left")
        create_credential_row(dialog, "Хост:", server_ip)
        create_credential_row(dialog, "Логин:", domain_info.get("ftp_user", "N/A"))
        create_credential_row(dialog, "Пароль:", domain_info.get("ftp_password", "N/A"))
        ctk.CTkButton(dialog, text="Закрыть", command=dialog.destroy).pack(pady=20)

    def toggle_domain_selection(self, domain, var):
        if var.get(): self.selected_domains.add(domain)
        else: self.selected_domains.discard(domain)
        if self.selected_domains:
            self.bind_cf_button.configure(state="normal")
            self.delete_domain_button.configure(state="normal")
        else:
            self.bind_cf_button.configure(state="disabled")
            self.delete_domain_button.configure(state="disabled")

    def update_domain_server(self, domain, server_ip):
        server = next((s for s in self.servers if s['ip'] == server_ip), None)
        server_id_to_save = server['id'] if server else None
        self.db.update_domain(domain, {"server_id": server_id_to_save})
        for d in self.domains:
            if d["domain_name"] == domain: d["server_id"] = server_id_to_save; break
        self.log_action(f"Для домена {domain} установлен сервер {server_ip}")
        self.show_success(f"Сервер для домена обновлен")

    def start_cloudflare_binding(self):
        # *** ИЗМЕНЕНИЕ: Проверяем и email тоже ***
        if not self.credentials.get("cloudflare_token") or not self.credentials.get("cloudflare_email"):
            self.show_error("Не указан API токен или E-mail для Cloudflare в настройках.")
            return

        if not self.credentials.get("namecheap_user") or not self.credentials.get("namecheap_key") or not self.credentials.get("namecheap_ip"):
            self.show_error("Не указаны все данные для Namecheap в настройках.")
            return

        for domain_name in self.selected_domains:
            domain_info = next((d for d in self.domains if d["domain_name"] == domain_name), None)
            if not domain_info or not domain_info.get("server_id"):
                self.show_error(f"Домен '{domain_name}' не ассоциирован с сервером.")
                return

        for domain_name in self.selected_domains:
            self.update_domain_status_ui(domain_name, "pending")
            thread = threading.Thread(target=self._bind_domain_thread, args=(domain_name,), daemon=True)
            thread.start()

    def _bind_domain_thread(self, domain_name):
        self.log_action(f"Начата привязка домена {domain_name} к Cloudflare.")
        domain_info = next((d for d in self.domains if d["domain_name"] == domain_name), None)
        server = next((s for s in self.servers if s['id'] == domain_info['server_id']), None)
        if not server:
            self.log_action(f"Не найден сервер для домена {domain_name}.", "ERROR")
            self.update_domain_status_ui(domain_name, "error"); return
        server_ip = server["ip"]
        
        # *** ИЗМЕНЕНИЕ: Передаем и email в сервис ***
        cf_service = CloudflareService(
            api_token=self.credentials.get("cloudflare_token"),
            email=self.credentials.get("cloudflare_email")
        )
        nc_service = NamecheapService(self.credentials.get("namecheap_user"), self.credentials.get("namecheap_key"), self.credentials.get("namecheap_ip"))
        
        zone_info = cf_service.add_zone(domain_name)
        if not zone_info:
            self.log_action(f"Ошибка добавления зоны {domain_name} в Cloudflare.", "ERROR")
            self.update_domain_status_ui(domain_name, "error"); return
        zone_id, name_servers = zone_info
        self.log_action(f"Зона {domain_name} успешно создана в Cloudflare.", "SUCCESS")

        if not cf_service.create_a_records(zone_id, server_ip):
            self.log_action(f"Ошибка создания A-записей для {domain_name}.", "ERROR")
            self.update_domain_status_ui(domain_name, "error"); return
        self.log_action(f"A-записи для {domain_name} созданы.", "SUCCESS")

        if not nc_service.update_nameservers(domain_name, name_servers):
            self.log_action(f"Ошибка обновления NS-серверов в Namecheap для {domain_name}", "ERROR")
            self.update_domain_status_ui(domain_name, "error"); return
        self.log_action(f"NS-записи для {domain_name} обновлены в Namecheap.", "SUCCESS")
        
        self.update_domain_status_ui(domain_name, "active", name_servers)
        self.log_action(f"Домен {domain_name} успешно привязан.", "SUCCESS")


    def start_ssl_issuance(self, domain_info):
        domain_name = domain_info['domain_name']
        if not domain_info.get("server_id"): self.show_error(f"Домен '{domain_name}' не привязан к серверу."); return
        if not self.app_settings.get("default_ssl_email"):
            self.show_error("Укажите Email в Настройках для выпуска SSL.")
            self.log_action("Попытка выпуска SSL без указания email в настройках.", "WARNING"); return
        self.log_action(f"Запуск выпуска SSL для домена {domain_name}")
        self.update_ssl_status_ui(domain_name, "pending")
        thread = threading.Thread(target=self._issue_ssl_thread, args=(domain_info,), daemon=True)
        thread.start()

    def _issue_ssl_thread(self, domain_info):
        domain_name = domain_info['domain_name']
        server = next((s for s in self.servers if s['id'] == domain_info['server_id']), None)
        if not server or not server.get('password'):
            self.log_action(f"Критическая ошибка: не найден сервер или пароль для домена {domain_name}", "ERROR")
            self.after(0, self.update_ssl_status_ui, domain_name, "error"); return
        service = FastPanelService()
        if not service.ssh.connect(server['ip'], server.get('ssh_user', 'root'), server.get('password')):
            self.log_action(f"Не удалось подключиться к серверу {server['ip']} для выпуска SSL.", "ERROR")
            self.after(0, self.update_ssl_status_ui, domain_name, "error"); return
        self.log_action(f"Подключились к {server['name']}, выпускаем сертификат для {domain_name}...")
        email = self.app_settings.get("default_ssl_email")
        result = service.issue_ssl_certificate(domain_name, email)
        service.ssh.disconnect()
        final_status = "active" if result['success'] else "error"
        if not result['success']: self.log_action(f"Ошибка выпуска SSL для {domain_name}: {result.get('error', 'Неизвестная ошибка')}", "ERROR")
        else: self.log_action(f"SSL-сертификат для {domain_name} успешно выпущен.", "SUCCESS")
        self.after(0, self.update_ssl_status_ui, domain_name, final_status)

    def update_ssl_status_ui(self, domain_name, status):
        def _update():
            self.db.update_domain(domain_name, {"ssl_status": status})
            for d in self.domains:
                if d["domain_name"] == domain_name: d["ssl_status"] = status; break
            if domain_name in self.domain_widgets:
                widgets = self.domain_widgets[domain_name]
                ssl_button = widgets["ssl_button"]
                
                if status == "active":
                    ssl_button.configure(text="Активен", fg_color="green", command=lambda d=domain_name: self.start_ssl_issuance(self.get_domain_info(d)))
                elif status == "pending":
                    ssl_button.configure(text="Выпускается...", state="disabled")
                elif status == "error":
                    ssl_button.configure(text="Ошибка", fg_color="red", command=lambda d=domain_name: self.start_ssl_issuance(self.get_domain_info(d)))
                else:
                    ssl_button.configure(text="Выпустить", command=lambda d=domain_name: self.start_ssl_issuance(self.get_domain_info(d)))

        self.after(0, _update)
    
    def get_domain_info(self, domain_name):
        return next((d for d in self.domains if d['domain_name'] == domain_name), None)

    def update_domain_status_ui(self, domain, status, ns_servers=None):
        def _update():
            update_data = {"cloudflare_status": status}
            if ns_servers: update_data["cloudflare_ns"] = ns_servers
            self.db.update_domain(domain, update_data)
            for d in self.domains:
                if d["domain_name"] == domain:
                    d["cloudflare_status"] = status
                    if ns_servers: d["cloudflare_ns"] = ",".join(ns_servers)
                    break
            if domain in self.domain_widgets:
                widget_refs = self.domain_widgets[domain]
                status_colors = { "none": ("#666666", "#aaaaaa"), "pending": ("#ff9800", "#f57c00"), "active": ("#4caf50", "#2e7d32"), "error": ("#f44336", "#d32f2f") }
                status_text = { "none": "⚪ Не привязан", "pending": "🟡 В процессе...", "active": "🟢 Активен", "error": "🔴 Ошибка" }
                widget_refs["status_label"].configure(text=status_text.get(status), text_color=status_colors.get(status))
                if ns_servers and "ns_label" in widget_refs: widget_refs["ns_label"].configure(text=", ".join(ns_servers))
                widget_refs["frame"].update_idletasks()
        self.after(0, _update)

    def show_add_domain_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Добавить домены")
        dialog.geometry("500x450")
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Добавить домены", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)
        server_ips = ["(Не выбран)"] + [s['ip'] for s in self.servers if s.get('ip')]
        server_var = ctk.StringVar(value=server_ips[0])
        ctk.CTkLabel(dialog, text="Привязать к серверу:").pack()
        server_menu = ctk.CTkOptionMenu(dialog, values=server_ips, variable=server_var)
        server_menu.pack(pady=(0,10))
        ctk.CTkLabel(dialog, text="Введите домены (каждый с новой строки):").pack()
        domain_textbox = ctk.CTkTextbox(dialog, height=200, width=400)
        domain_textbox.pack(pady=10)
        ctk.CTkButton(dialog, text="Сохранить", command=lambda: self.add_domains(domain_textbox.get("1.0", "end-1c"), server_var.get(), dialog)).pack(pady=20)

    def add_domains(self, domains_text, server_ip, dialog):
        dialog.destroy() # Close dialog immediately to provide user feedback
        domains = [d.strip() for d in domains_text.split("\n") if d.strip()]
        if not domains:
            return

        server = next((s for s in self.servers if s['ip'] == server_ip), None)
        server_id_to_save = server['id'] if server else None
        
        added_count = 0
        existing_domains = []
        for domain in domains:
            # Set default purchase date to today
            domain_data = {
                "domain_name": domain, 
                "server_id": server_id_to_save,
                "purchase_date": datetime.now().strftime("%Y-%m-%d")
            }
            if self.db.add_domain(domain_data):
                added_count += 1
            else:
                existing_domains.append(domain)

        if added_count > 0:
            self.log_action(f"Добавлено {added_count} новых доменов.")
            self.show_success(f"Добавлено {added_count} доменов.")
            self.refresh_data() # This is the key change: reload all data from DB
        
        if existing_domains:
            self.show_error(f"Домены уже существуют: {', '.join(existing_domains)}")


    def show_result_tab(self):
        self.clear_tab_container()
        self.page_title.configure(text="Результаты установки")
        self.current_tab = "result"
        result_textbox = ctk.CTkTextbox(self.tab_container, wrap="word")
        result_textbox.pack(fill="both", expand=True)
        result_text = ""
        for server in self.servers:
            if server.get("fastpanel_installed"): result_text += f"{server['ip']};user{server['id']};pass{server['id']}\n"
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
        tab_view = ctk.CTkTabview(self.tab_container, fg_color=("#ffffff", "#2b2b2b"))
        tab_view.pack(fill="both", expand=True, padx=20, pady=10)
        general_tab = tab_view.add("Общие")
        cf_tab = tab_view.add("Cloudflare")
        nc_tab = tab_view.add("Namecheap")
        self._create_general_settings_tab(general_tab)
        self._create_cloudflare_settings_tab(cf_tab)
        self._create_namecheap_settings_tab(nc_tab)

    def _create_general_settings_tab(self, parent):
        ctk.CTkLabel(parent, text="Общие настройки", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))
        self.ssl_email_entry = self._create_setting_row(parent, "Email для SSL:")
        self.ssl_email_entry.insert(0, self.app_settings.get("default_ssl_email", ""))
        self._create_save_cancel_buttons(parent, self.save_all_settings)

    def _create_cloudflare_settings_tab(self, parent):
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header_frame, text="Настройки Cloudflare API", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(header_frame, text="Как получить API?", command=self.show_cloudflare_instructions).pack(side="left", padx=10)

        # *** ИЗМЕНЕНИЕ: Добавлено поле для E-mail ***
        self.cf_email_entry = self._create_setting_row(parent, "E-mail аккаунта:")
        self.cf_email_entry.insert(0, self.credentials.get("cloudflare_email", ""))

        self.cf_token_entry = self._create_setting_row(parent, "Global API Key:")
        self.cf_token_entry.insert(0, self.credentials.get("cloudflare_token", ""))
        self.cf_token_entry.configure(show="*")
        self._create_save_cancel_buttons(parent, self.save_all_settings)


    def _create_namecheap_settings_tab(self, parent):
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header_frame, text="Настройки Namecheap API", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(header_frame, text="Как получить API?", command=self.show_namecheap_instructions).pack(side="left", padx=10)

        self.nc_user_entry = self._create_setting_row(parent, "API User:")
        self.nc_user_entry.insert(0, self.credentials.get("namecheap_user", "sergeyivanov"))
        self.nc_key_entry = self._create_setting_row(parent, "API Key:")
        self.nc_key_entry.insert(0, self.credentials.get("namecheap_key", ""))
        self.nc_key_entry.configure(show="*")
        ip_frame = self._create_setting_row(parent, "Whitelist IP:", return_frame=True)
        self.nc_ip_entry = ctk.CTkEntry(ip_frame, width=250)
        self.nc_ip_entry.pack(side="left")
        self.nc_ip_entry.insert(0, self.credentials.get("namecheap_ip", ""))
        ctk.CTkButton(ip_frame, text="Получить мой IP", width=120, command=self.fetch_public_ip).pack(side="left", padx=10)
        self._create_save_cancel_buttons(parent, self.save_all_settings)

    def show_namecheap_instructions(self):
        instruction_text = """
Как получить API-ключ в Namecheap:

1. Зайди в аккаунт Namecheap: https://ap.www.namecheap.com/
2. Открой раздел управления профилем:
   В верхнем меню выбери Profile → Tools → Namecheap API Access 
   (или сразу перейди по ссылке: https://ap.www.namecheap.com/settings/tools/apiaccess/).
3. Включи API-доступ:
   Нажми 'Enable API Access'.
   Тебе нужно будет указать статический IP-адрес сервера, с которого будут идти запросы (Namecheap принимает только whitelisted IP).
4. Сгенерируй ключ:
   API Key генерируется автоматически после активации доступа.
   Ты его увидишь в разделе API Access (и сможешь сгенерировать новый, если понадобится).
5. Используй связку:
   - API Username → это твой логин от Namecheap (например: sergeyivanov)
   - API Key → сгенерированный ключ.
   - API IP → IP, который ты добавил в белый список.
"""
        InstructionWindow(self, "Инструкция по Namecheap API", instruction_text)

    def show_cloudflare_instructions(self):
        instruction_text = """
Как получить глобальный API-ключ в Cloudflare:

1. Зайди в аккаунт: https://dash.cloudflare.com/
2. В правом верхнем углу нажми на иконку профиля → My Profile.
3. Перейди во вкладку 'API Tokens'.
4. Тебе нужен 'Global API Key'.
5. Для получения глобального ключа:
   - Нажми 'View' → 'Global API Key'.
   - Введи пароль от аккаунта.
   - Ключ появится на экране — сохрани его.
"""
        InstructionWindow(self, "Инструкция по Cloudflare API", instruction_text)

    def _create_setting_row(self, parent, label_text, return_frame=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=10, expand=True)
        label = ctk.CTkLabel(row, text=label_text, width=180, anchor="w")
        label.pack(side="left")
        if return_frame:
            content_frame = ctk.CTkFrame(row, fg_color="transparent")
            content_frame.pack(side="left", fill="x", expand=True)
            return content_frame
        entry = ctk.CTkEntry(row, width=350)
        entry.pack(side="left", fill="x", expand=True)
        return entry

    def _create_save_cancel_buttons(self, parent, save_command):
        buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
        buttons_frame.pack(pady=20, padx=20, fill="x")
        ctk.CTkButton(buttons_frame, text="Сохранить", width=120, command=save_command).pack(side="right")
        ctk.CTkButton(buttons_frame, text="Отмена", width=120, fg_color="transparent", border_width=1, command=self.show_servers_tab).pack(side="right", padx=10)

    def fetch_public_ip(self):
        self.nc_ip_entry.delete(0, "end")
        self.nc_ip_entry.insert(0, "Получение...")
        threading.Thread(target=self._get_ip_thread, daemon=True).start()

    def _get_ip_thread(self):
        ip = NamecheapService.get_public_ip()
        self.after(0, lambda: (self.nc_ip_entry.delete(0, "end"), self.nc_ip_entry.insert(0, ip)))

    def save_all_settings(self):
        # *** ИЗМЕНЕНИЕ: Сохраняем и E-mail ***
        self.credentials["cloudflare_email"] = self.cf_email_entry.get()
        self.credentials["cloudflare_token"] = self.cf_token_entry.get()
        self.credentials["namecheap_user"] = self.nc_user_entry.get()
        self.credentials["namecheap_key"] = self.nc_key_entry.get()
        self.credentials["namecheap_ip"] = self.nc_ip_entry.get()
        for key, value in self.credentials.items(): self.db.save_setting(key, value)
        
        self.app_settings["default_ssl_email"] = self.ssl_email_entry.get()
        for key, value in self.app_settings.items(): self.db.save_setting(key, value)
        
        self.show_success("Настройки сохранены")
        self.log_action("Настройки приложения сохранены")

    def load_data_from_db(self):
        self.servers = self.db.get_all_servers()
        for server in self.servers:
            self.server_statuses[server['id']] = "idle" # Initialize all servers as idle
        self.domains = self.db.get_all_domains()
        all_settings = self.db.get_all_settings()
        
        # *** ИЗМЕНЕНИЕ: Добавляем 'cloudflare_email' в ключи credentials ***
        cred_keys = ["cloudflare_token", "cloudflare_email", "namecheap_user", "namecheap_key", "namecheap_ip"]
        self.credentials = {k: v for k, v in all_settings.items() if k in cred_keys}
        self.app_settings = {k: v for k, v in all_settings.items() if k not in cred_keys}
        
        self.log_action(f"Загружено {len(self.servers)} серверов и {len(self.domains)} доменов из БД.")


    def show_monitoring_tab(self):
        self.clear_tab_container()
        self.page_title.configure(text="Мониторинг серверов")
        self.current_tab = "monitoring"
        
        scroll_frame = ctk.CTkScrollableFrame(self.tab_container, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)

        if not self.servers:
            ctk.CTkLabel(scroll_frame, text="Нет серверов для мониторинга").pack(pady=50)
            return
        
        self.monitoring_cards = {}
        for i, server in enumerate(self.servers):
            card = ctk.CTkFrame(scroll_frame, corner_radius=10, border_width=1)
            card.pack(fill="x", pady=5, padx=5)
            
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=15, pady=10)
            ctk.CTkLabel(header, text=f"🖥️ {server['name']} ({server['ip']})", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

            metrics_frame = ctk.CTkFrame(card, fg_color="transparent")
            metrics_frame.pack(fill="x", padx=15, pady=10)
            metrics_frame.grid_columnconfigure((0,1,2), weight=1)

            def create_metric(parent, name, row, col):
                frame = ctk.CTkFrame(parent, fg_color="transparent")
                frame.grid(row=row, column=col, sticky="ew", padx=10)
                label = ctk.CTkLabel(frame, text=f"{name}: 0%", font=ctk.CTkFont(size=12))
                label.pack()
                progress = ctk.CTkProgressBar(frame)
                progress.set(0)
                progress.pack(fill="x")
                return label, progress
            
            cpu_label, cpu_progress = create_metric(metrics_frame, "CPU", 0, 0)
            ram_label, ram_progress = create_metric(metrics_frame, "RAM", 0, 1)
            disk_label, disk_progress = create_metric(metrics_frame, "Disk", 0, 2)

            self.monitoring_cards[server['id']] = {
                "card": card, "cpu_label": cpu_label, "cpu_progress": cpu_progress,
                "ram_label": ram_label, "ram_progress": ram_progress,
                "disk_label": disk_label, "disk_progress": disk_progress
            }
        
        self.update_monitoring_ui()

    def update_monitoring_ui(self):
        if self.current_tab != "monitoring":
            return
            
        for server_id, metrics in self.server_metrics.items():
            if server_id in self.monitoring_cards:
                card_widgets = self.monitoring_cards[server_id]
                
                cpu = metrics.get('cpu', 0)
                ram = metrics.get('ram', 0)
                disk = metrics.get('disk', 0)
                
                card_widgets['cpu_label'].configure(text=f"CPU: {cpu}%")
                card_widgets['cpu_progress'].set(cpu / 100)
                card_widgets['ram_label'].configure(text=f"RAM: {ram}%")
                card_widgets['ram_progress'].set(ram / 100)
                card_widgets['disk_label'].configure(text=f"Disk: {disk}%")
                card_widgets['disk_progress'].set(disk / 100)

                if cpu > 90 or ram > 90 or disk > 90:
                    card_widgets['card'].configure(border_color="red")
                else:
                    card_widgets['card'].configure(border_color=("#e0e0e0", "#404040"))

    def start_monitoring(self):
        monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        monitor_thread.start()

    def _monitoring_loop(self):
        while True:
            for server in self.servers:
                server_id = server['id']
                if self.server_statuses.get(server_id) != "idle":
                    self.log_action(f"Мониторинг сервера {server['name']} пропущен (статус: {self.server_statuses.get(server_id)})", "DEBUG")
                    continue

                if not server.get('password'): continue

                self.server_statuses[server_id] = "monitoring"
                ssh = SSHManager()
                if ssh.connect(server['ip'], server.get('ssh_user', 'root'), server.get('password')):
                    # CPU
                    cpu_result = ssh.execute("top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'")
                    # RAM
                    ram_result = ssh.execute("free | grep Mem | awk '{print $3/$2 * 100.0}'")
                    # Disk
                    disk_result = ssh.execute("df -h / | tail -n 1 | awk '{print $5}' | sed 's/%//'")
                    
                    self.server_metrics[server_id] = {
                        'cpu': float(cpu_result.stdout.strip()) if cpu_result.success else 0,
                        'ram': float(ram_result.stdout.strip()) if ram_result.success else 0,
                        'disk': int(disk_result.stdout.strip()) if disk_result.success else 0,
                    }
                    ssh.disconnect()
                self.server_statuses[server_id] = "idle"
            
            self.after(0, self.update_monitoring_ui)
            time.sleep(3600) # 1 hour

    def show_logs_tab(self, level_filter="Все"):
        self.clear_tab_container()
        self.page_title.configure(text="Логи")
        self.current_tab = "logs"
        filter_frame = ctk.CTkFrame(self.tab_container, fg_color="transparent")
        filter_frame.pack(fill="x", pady=(0, 10))
        levels = ["Все", "INFO", "SUCCESS", "WARNING", "ERROR"]
        for level in levels:
            btn = ctk.CTkButton(filter_frame, text=level, command=lambda l=level: self.show_logs_tab(l))
            btn.pack(side="left", padx=5)
        logs_text = ctk.CTkTextbox(self.tab_container, wrap="word")
        logs_text.pack(fill="both", expand=True)
        log_colors = {"INFO": "#FFFFFF", "SUCCESS": "#00C853", "WARNING": "#FFAB00", "ERROR": "#D50000"}
        for level, color in log_colors.items(): logs_text.tag_config(level, foreground=color)
        for log in self.logs:
            if level_filter == "Все" or level_filter in log:
                try:
                    level = log.split(": ")[0].split("] ")[1]
                    if level not in log_colors: level = "INFO"
                    logs_text.insert("end", log + "\n", level)
                except IndexError: logs_text.insert("end", log + "\n", "INFO")
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
        for widget in self.tab_container.winfo_children(): widget.destroy()

    def handle_server_action(self, action, server_data):
        actions = {
            "manage": self.show_server_management, "install": self.start_installation,
            "open_panel": lambda s: webbrowser.open(s.get("admin_url")) if s.get("admin_url") else None,
            "delete": self.confirm_delete_server, "edit": self.show_add_server_tab,
            "start_automation": self.start_automation, "show_log": self.show_log_window,
        }
        if action in actions: actions[action](server_data)

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
        info_items = [("ID", data.get("id")), ("Название", data.get("name")), ("IP", data.get("ip")), ("SSH порт", data.get("ssh_port", 22)), ("SSH пользователь", data.get("ssh_user")), ("Дата добавления", data.get("created_at", "N/A").split(" ")[0])]
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
            fp_items = [("URL", data.get("admin_url", f"https://{data.get('ip')}:8888")), ("Логин", "fastuser")]
            for label, value in fp_items:
                row = ctk.CTkFrame(fp_content, fg_color="transparent")
                row.pack(fill="x", pady=5)
                ctk.CTkLabel(row, text=f"{label}:", width=150, anchor="w", text_color=("#666666", "#aaaaaa")).pack(side="left")
                ctk.CTkLabel(row, text=str(value)).pack(side="left")
            pass_row = ctk.CTkFrame(fp_content, fg_color="transparent")
            pass_row.pack(fill="x", pady=5)
            ctk.CTkLabel(pass_row, text="Пароль:", width=150, anchor="w", text_color=("#666666", "#aaaaaa")).pack(side="left")
            password = data.get("admin_password", "Не сохранен")
            pass_label = ctk.CTkLabel(pass_row, text="••••••••" if password else "Не сохранен")
            pass_label.pack(side="left")
            def toggle_password():
                if pass_label.cget("text") == "••••••••": pass_label.configure(text=password)
                else: pass_label.configure(text="••••••••")
            if password: ctk.CTkButton(pass_row, text="👁️", width=30, command=toggle_password).pack(side="left", padx=10)

    def _create_sites_tab(self, parent, server_data):
        sites_frame = ctk.CTkFrame(parent, fg_color="transparent")
        sites_frame.pack(fill="both", expand=True)
        sites_list_frame = ctk.CTkScrollableFrame(sites_frame, fg_color="transparent")
        sites_list_frame.pack(fill="both", expand=True)
        server_domains = [d for d in self.domains if d.get("server_id") == server_data.get("id")]
        if not server_domains:
            ctk.CTkLabel(sites_list_frame, text="На этом сервере нет сайтов").pack(pady=20)
        else:
            for domain_info in server_domains:
                site_card = ctk.CTkFrame(sites_list_frame, fg_color=("#ffffff", "#2b2b2b"), corner_radius=8)
                site_card.pack(fill="x", pady=5)
                site_content = ctk.CTkFrame(site_card, fg_color="transparent")
                site_content.pack(padx=15, pady=12, fill="x")
                ctk.CTkLabel(site_content, text=f"🌐 {domain_info['domain_name']}", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", anchor="w")
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

    def show_log_window(self, server_data):
        server_id = server_data.get("id")
        if not server_id in self.installation_states: return
        state = self.installation_states[server_id]
        if state.get("log_window"): state["log_window"].lift(); return
        log_window = ctk.CTkToplevel(self)
        log_window.title(f"Лог установки: {server_data['name']}")
        log_window.geometry("700x500")
        state["log_window"] = log_window
        log_window.log_text = ctk.CTkTextbox(log_window, wrap="word")
        log_window.log_text.pack(fill="both", expand=True, padx=10, pady=(10,0))
        log_window.log_text.insert("1.0", "\n".join(state["log"]))
        log_window.log_text.see("end")
        def copy_log():
            self.clipboard_clear()
            self.clipboard_append(log_window.log_text.get("1.0", "end"))
        ctk.CTkButton(log_window, text="Копировать лог", command=copy_log).pack(pady=10)
        def on_close():
            state["log_window"] = None
            log_window.destroy()
        log_window.protocol("WM_DELETE_WINDOW", on_close)

    def log_action(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs.append(f"[{timestamp}] {level}: {message}")
        if self.current_tab == "logs": self.show_logs_tab()

    def show_success(self, message):
        self.status_label.configure(text=f"✅ {message}", text_color=("#4caf50", "#4caf50"))
        self.after(3000, lambda: self.status_label.configure(text="● Готов к работе", text_color=("#4caf50", "#4caf50")))

    def show_error(self, message):
        self.status_label.configure(text=f"❌ {message}", text_color=("#f44336", "#f44336"))
        self.log_action(message, level="ERROR")
        self.after(3000, lambda: self.status_label.configure(text="● Готов к работе", text_color=("#4caf50", "#4caf50")))
    
    def check_server_renewals(self):
        expiring_servers = 0
        today = datetime.now()
        for server in self.servers:
            try:
                created_at = datetime.strptime(server['created_at'].split("T")[0], "%Y-%m-%d")
                period = timedelta(days=int(server.get('hosting_period_days', 30)))
                renewal_date = created_at + period
                if (renewal_date - today).days <= 3:
                    expiring_servers += 1
            except (ValueError, TypeError):
                continue
        
        btn = self.nav_buttons["Серверы"]
        if expiring_servers > 0:
            btn.configure(text=f"🖥️ Серверы 🔔({expiring_servers})")
        else:
            btn.configure(text="🖥️ Серверы")


    def start_automation(self, server_data):
        server_id = server_data['id']
        self.server_statuses[server_id] = "automating"
        self.log_action(f"Запуск автоматизации для сервера '{server_data['name']}'")
        self.show_success(f"Автоматизация для '{server_data['name']}' запущена...")
        server_domains = [d for d in self.domains if d.get("server_id") == server_data.get("id")]
        if not server_domains:
            self.log_action(f"На сервере '{server_data['name']}' нет привязанных доменов.", level="WARNING")
            self.show_error("Нет доменов для автоматизации"); return
        progress_window = AutomationProgressWindow(self, server_data['name'], len(server_domains))
        automation_thread = threading.Thread(target=self._run_automation_in_thread, args=(server_data, server_domains, progress_window), daemon=True)
        automation_thread.start()

    def _run_automation_in_thread(self, server_data, domains_to_process, progress_window):
        server_id = server_data['id']
        def progress_callback(message):
            self.after(0, progress_window.add_log, message)
            self.log_action(message)
        progress_callback(f"Всего доменов для автоматизации: {len(domains_to_process)}")
        service = FastPanelService(fastpanel_path=self.app_settings.get("fastpanel_path"))
        if not service.ssh.connect(server_data['ip'], server_data.get('ssh_user', 'root'), server_data.get('password')):
            progress_callback(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к серверу {server_data['ip']}.")
            self.log_action(f"SSH-соединение не установлено для {server_data['name']}", "ERROR")
            self.after(0, progress_window.destroy)
            self.server_statuses[server_id] = "idle"
            return
        progress_callback("SSH-соединение успешно установлено.")
        for domain_info in domains_to_process:
            progress_callback(f"--- Начало работы с доменом: {domain_info['domain_name']} ---")
            domain_info_adapted = {'domain_name': domain_info['domain_name']}
            ssl_email = self.app_settings.get("default_ssl_email")
            updated_data = service.run_domain_automation(domain_info_adapted, server_data, progress_callback, ssl_email)
            self.after(0, self._update_domain_data, updated_data)
            self.after(0, progress_window.increment_progress)
        service.ssh.disconnect()
        progress_callback("--- Автоматизация завершена ---")
        self.log_action(f"Автоматизация для сервера '{server_data['name']}' завершена.", "SUCCESS")
        self.server_statuses[server_id] = "idle"
        self.after(5000, progress_window.destroy)

    def _update_domain_data(self, updated_domain_info):
        domain_name = updated_domain_info.get("domain_name")
        if not domain_name: return
        self.db.update_domain(domain_name, updated_domain_info)
        for i, d in enumerate(self.domains):
            if d.get('domain_name') == domain_name: self.domains[i].update(updated_domain_info); break
        if self.current_tab == "domain": self.show_domain_tab()

if __name__ == "__main__":
    app = FastPanelApp()
    app.mainloop()
