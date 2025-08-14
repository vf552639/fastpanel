# FastPanel Automation MVP

Минимальная рабочая версия системы автоматизации FastPanel для быстрого старта.

## 🚀 Быстрый старт

### Требования
- Python 3.8+
- SSH доступ к серверам
- Ubuntu/Debian серверы для установки FastPanel

### Установка

1. **Клонируйте репозиторий:**
```bash
git clone <your-repo>
cd fastpanel-automation
```

2. **Создайте виртуальное окружение:**
```bash
python3 -m venv venv
```

3. **Установите зависимости:**
```bash
pip install -r requirements.txt
```

4. **Запустите приложение:**
```bash
python src/main.py
```

## 📁 Структура проекта

```
fastpanel-automation/
├── src/
│   ├── main.py              # Точка входа - CLI интерфейс
│   ├── config.py            # Конфигурация приложения
│   ├── core/
│   │   ├── ssh_manager.py   # SSH подключения
│   │   └── security.py      # (будущее) Шифрование
│   ├── services/
│   │   ├── fastpanel.py     # Работа с FastPanel
│   │   └── cloudflare.py    # (будущее) Cloudflare API
│   └── utils/
│       └── logger.py        # Логирование
├── data/                    # Локальное хранилище
│   └── servers.json         # База серверов
├── logs/                    # Логи приложения
└── requirements.txt         # Зависимости
```

## 🎯 Основные функции MVP

- ✅ Добавление серверов
- ✅ SSH подключение к серверам
- ✅ Установка FastPanel одной командой
- ✅ Сохранение данных для входа
- ✅ Простой текстовый интерфейс

## 🔧 Использование

### CLI интерфейс

При запуске `python src/main.py` вы увидите меню:

```
==================================================
🚀 FastPanel Automation MVP
==================================================
1. Добавить сервер
2. Установить FastPanel
3. Список серверов
0. Выход
```

### Программное использование

```python
from src.core.ssh_manager import SSHManager
from src.services.fastpanel import FastPanelService

# Подключение к серверу
ssh = SSHManager()
ssh.connect("192.168.1.100", username="root", password="your_password")

# Установка FastPanel
fp_service = FastPanelService(ssh)
result = fp_service.install("192.168.1.100", "root", "your_password")

if result['success']:
    print(f"Admin URL: {result['admin_url']}")
    print(f"Admin Password: {result['admin_password']}")
```

## 📝 Логирование

Все операции логируются в `logs/automation.log`. Уровень логирования можно изменить через переменную окружения:

```bash
export FP_DEBUG=true  # Включить отладку
```

## 🔐 Безопасность

**Важно:**
- Пароли хранятся в открытом виде (будет исправлено в следующих версиях)
- Используйте SSH ключи вместо паролей где возможно
- Не коммитьте файлы из папки `data/` в git
- Регулярно обновляйте зависимости: `pip install --upgrade -r requirements.txt`

## 🚧 Планы развития

### Версия 0.2.0
- [ ] Шифрование паролей
- [ ] Поддержка SSH ключей
- [ ] Базовый GUI интерфейс

### Версия 0.3.0
- [ ] Интеграция с Cloudflare API
- [ ] Автоматическая настройка SSL
- [ ] Массовые операции

### Версия 1.0.0
- [ ] Полноценный GUI
- [ ] База данных вместо JSON
- [ ] API для интеграций
- [ ] Docker контейнер

## 🐛 Известные проблемы

1. **Пароль администратора не извлекается автоматически**
   - Решение: Проверьте вывод установки в логах

2. **Timeout при установке на слабых серверах**
   - Решение: Увеличьте timeout в `config.py`

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте ветку для фичи (`git checkout -b feature/amazing`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в ветку (`git push origin feature/amazing`)
5. Создайте Pull Request

## 📄 Лицензия

MIT

## 📞 Поддержка

- Создайте Issue в GitHub
- Email: your-email@example.com

---

**Статус проекта:** MVP ✅ | В активной разработке 🚀
