import json
import sys
import requests
import os
from getpass import getpass

DATA_DIR = os.getenv('DATA_DIR', 'data')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
IP_FILE = os.path.join(DATA_DIR, 'ip.txt')
COOKIES_FILE = os.path.join(DATA_DIR, 'cookies.json')

IP_SERVICES = [
    'https://api.ipify.org?format=json',
    'https://wtfismyip.com/text',
    'https://api.myip.com/'
]

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print("✅ Настройки сохранены.")


def initial_setup():
    print("--- Первоначальная настройка Timeweb DDNS ---")
    config = {}
    config["timeweb_login"] = input("Введите логин от Timeweb: ")
    config["timeweb_password"] = getpass("Введите пароль от Timeweb: ")
    domains_raw = input("Введите домены и поддомены через запятую (например, domain.ru,sub.domain.ru): ")
    config["domains"] = [d.strip() for d in domains_raw.split(',') if d.strip()]
    browser_choice = input("Какой браузер использовать? (chrome/firefox) [chrome]: ").lower() or "chrome"
    if browser_choice not in ["chrome", "firefox"]:
        print("Неверный выбор. Используем 'chrome' по умолчанию.")
        browser_choice = "chrome"
    config["browser"] = browser_choice
    save_config(config)
    print(f"✅ Конфигурация создана в {CONFIG_FILE}\n")
    return config

def clear_session():
    if os.path.exists(IP_FILE):
        os.remove(IP_FILE)
        print(f"ℹ️  Файл {IP_FILE} удален.")
    if os.path.exists(COOKIES_FILE):
        os.remove(COOKIES_FILE)
        print(f"ℹ️  Файл {COOKIES_FILE} удален.")
    print("✅ Сессия сброшена.")

def manage_settings():
    try:
        config = load_config(setup_if_missing=False)
    except FileNotFoundError:
        print("Файл конфигурации не найден. Запускаю первоначальную настройку.")
        initial_setup()
        return

    while True:
        print("\n--- Управление настройками ---")
        print(f"1. Изменить логин (текущий: {config['timeweb_login']})")
        print(f"2. Изменить пароль (текущий: ******)")
        print(f"3. Изменить список доменов (текущий: {', '.join(config['domains'])})")
        print(f"4. Изменить браузер (текущий: {config.get('browser', 'chrome')})")
        print(f"5. Изменить интервал проверки (текущий: {config.get('check_interval_minutes', 30)} мин.)")
        print("6. Назад в главное меню")

        choice = input("Выберите, что хотите изменить: ")

        if choice == '1':
            config['timeweb_login'] = input("Введите новый логин: ")
            save_config(config)
        elif choice == '2':
            config['timeweb_password'] = getpass("Введите новый пароль: ")
            save_config(config)
        elif choice == '3':
            domains_raw = input("Введите новый список доменов через запятую: ")
            config['domains'] = [d.strip() for d in domains_raw.split(',') if d.strip()]
            save_config(config)
        elif choice == '4':
            browser_choice = input(
                f"Какой браузер использовать? (chrome/firefox) [{config.get('browser', 'chrome')}]: ").lower() or config.get(
                'browser', 'chrome')
            config['browser'] = "firefox" if browser_choice == "firefox" else "chrome"
            save_config(config)
        elif choice == '5':
            try:
                new_interval = int(input("Введите новый интервал проверки в минутах: "))
                if new_interval > 0:
                    config['check_interval_minutes'] = new_interval
                    save_config(config)
                else:
                    print("❌ Интервал должен быть больше нуля.")
            except ValueError:
                print("❌ Пожалуйста, введите число.")
        elif choice == '6':
            break
        else:
            print("Неверный ввод.")


def load_config(setup_if_missing=True):
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                print(f"🟡 Предупреждение: Файл {CONFIG_FILE} поврежден или пуст.")
                pass

    config['timeweb_login'] = os.getenv('TIMEWEB_LOGIN', config.get('timeweb_login'))
    config['timeweb_password'] = os.getenv('TIMEWEB_PASSWORD', config.get('timeweb_password'))

    domains_env = os.getenv('TIMEWEB_DOMAINS')
    if domains_env:
        config['domains'] = [d.strip() for d in domains_env.split(',')]

    if not config.get('timeweb_login') or not config.get('timeweb_password'):
        if setup_if_missing and sys.stdout.isatty():
            print("Логин/пароль не найдены в config.json или переменных окружения.")
            return initial_setup()
        else:
            print("❌ Ошибка: TIMEWEB_LOGIN и TIMEWEB_PASSWORD должны быть установлены в .env файле для Docker.")
            return None

    if 'domains' not in config: config['domains'] = []
    if 'browser' not in config: config['browser'] = 'chrome'
    if 'check_interval_minutes' not in config: config['check_interval_minutes'] = 30

    return config


def get_current_ip():
    for service_url in IP_SERVICES:
        try:
            response = requests.get(service_url, timeout=5)
            response.raise_for_status()

            if 'ipify' in service_url:
                return response.json()['ip']
            else:
                return response.text.strip()

        except requests.RequestException as e:
            print(f"🟡  Сервис {service_url} недоступен, пробую следующий...")
            continue

    print("❌ Не удалось получить внешний IP ни от одного из сервисов.")
    return None


def get_saved_ip():
    if os.path.exists(IP_FILE):
        with open(IP_FILE, 'r') as f:
            return f.read().strip()
    return None


def save_new_ip(ip):
    with open(IP_FILE, 'w') as f:
        f.write(ip)