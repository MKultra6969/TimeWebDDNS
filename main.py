import sys
import time
from utils import load_config, manage_settings, get_current_ip, get_saved_ip, save_new_ip, clear_session
from dns_updater import TimeWebManager, update_dns_records


def run_update(force=False):
    if force:
        print("▶️  Запуск принудительного обновления IP...")
    else:
        print("▶️  Запуск проверки IP...")

    config = load_config()
    if not config:
        print("❌ Не удалось загрузить конфигурацию. Выход.")
        return

    current_ip = get_current_ip()
    if not current_ip:
        return

    saved_ip = get_saved_ip()
    print(f"Текущий IP: {current_ip}")
    print(f"Сохраненный IP: {saved_ip or 'не найден'}")

    if current_ip == saved_ip and not force:
        print("✅ IP-адрес не изменился. Обновление не требуется.")
        return

    if force and current_ip == saved_ip:
        print("ℹ️  IP-адрес не изменился, но обновление будет выполнено принудительно.")
    else:
        print(f"⚠️ IP-адрес изменился! Старый: {saved_ip}, Новый: {current_ip}")

    print("Начинаю обновление DNS записей (это может занять несколько минут)...")
    success = update_dns_records(config, current_ip)

    if success:
        save_new_ip(current_ip)
        print("\n✅ DNS записи успешно обновлены, новый IP сохранен.")
    else:
        print("\n❌ Произошла ошибка при обновлении DNS записей. IP не был сохранен.")


def run_auto_mode():
    print("--- Запуск в автоматическом режиме ---")
    config = load_config()
    interval_minutes = config.get("check_interval_minutes", 30)
    interval_seconds = interval_minutes * 60

    while True:
        try:
            run_update()
            print(f"\n--- Проверка завершена. Следующая проверка через {interval_minutes} минут. ---")
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nВыход из автоматического режима.")
            break
        except Exception as e:
            print(f"\n❌ Произошла критическая ошибка в цикле: {e}")
            print(f"Повторная попытка через {interval_minutes} минут...")
            time.sleep(interval_seconds)


def manual_edit_menu():
    config = load_config()
    manager = TimeWebManager(config)

    try:
        print("\n▶️  Подключаюсь к Timeweb (это может занять минуту)...")
        if not manager.login():
            print("❌ Не удалось авторизоваться. Возврат в главное меню.")
            return

        records = manager.get_a_records()

        if records is None:
            print("❌ Не удалось получить DNS-записи. Проверьте лог ошибок выше.")
            return

        while True:
            print("\n--- Текущие A-записи (активная сессия) ---")
            domain_list = list(records.keys())
            for i, domain in enumerate(domain_list):
                ip = records.get(domain, "неизвестно")
                print(f"{i + 1}. {domain} -> {ip}")
            print("0. Назад в главное меню (сессия закроется)")

            try:
                choice = int(input("\nВыберите домен для редактирования (введите номер) или 0 для выхода: "))
                if choice == 0:
                    break

                if 1 <= choice <= len(domain_list):
                    selected_domain = domain_list[choice - 1]
                    new_ip = input(f"Введите новый IP для '{selected_domain}': ").strip()
                    if not new_ip:
                        print("❌ IP-адрес не может быть пустым. Отмена.")
                        continue

                    print(f"\n▶️  Обновляю IP для {selected_domain} на {new_ip}...")

                    success = manager.update_single_record(selected_domain, new_ip)

                    if success:
                        print(f"✅ Запись для {selected_domain} успешно обновлена.")
                        records[selected_domain] = new_ip
                    else:
                        print(f"❌ Не удалось обновить запись для {selected_domain}.")

                    input("Нажмите Enter, чтобы продолжить...")

                else:
                    print("❌ Неверный номер. Пожалуйста, выберите из списка.")

            except ValueError:
                print("❌ Пожалуйста, введите число.")

    finally:
        manager.close()


def main_menu():
    while True:
        print("\n--- Меню Timeweb DDNS ---")
        print("1. Проверить и обновить IP (стандартный режим)")
        print("2. Принудительно обновить IP (даже если он не менялся)")
        print("3. Посмотреть/изменить A-записи вручную")
        print("4. Изменить настройки")
        print("5. Сбросить сессию (для новой авторизации)")
        print("6. Выход")

        choice = input("Выберите действие: ")

        if choice == '1':
            run_update()
        elif choice == '2':
            run_update(force=True)
        elif choice == '3':
            manual_edit_menu()
        elif choice == '4':
            manage_settings()
        elif choice == '5':
            clear_session()
        elif choice == '6':
            print("Выход.")
            break
        else:
            print("Неверный ввод. Пожалуйста, выберите пункт меню.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'auto':
            run_auto_mode()
        elif command == 'force-update':
            run_update(force=True)
        else:
            print(f"Неизвестная команда: {command}")
    else:
        main_menu()