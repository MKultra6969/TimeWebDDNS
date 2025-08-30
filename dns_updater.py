import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Chrome
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

# Firefox
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

DATA_DIR = os.getenv('DATA_DIR', '.')
COOKIES_FILE = os.path.join(DATA_DIR, 'cookies.json')


class TimeWebManager:

    def __init__(self, config):
        self.config = config
        self.driver = None
        self.wait = None
        self.logged_in = False

    def _initialize_driver(self):
        browser_type = self.config.get("browser", "chrome").lower()
        user_agent = "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0"

        if browser_type == "firefox":
            print("  - Используем Firefox")
            options = webdriver.FirefoxOptions()
            options.add_argument("--headless")
            options.add_argument("--width=1920")
            options.add_argument("--height=1080")
            options.set_preference("general.useragent.override", user_agent)
            options.set_preference("dom.webdriver.enabled", False)
            options.set_preference('useAutomationExtension', False)
            service = FirefoxService(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        else:
            print("  - Используем Chrome")
            options = webdriver.ChromeOptions()
            options.binary_location = "/usr/bin/google-chrome"
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument(f'user-agent={user_agent}')
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',
                                        {
                                            'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})
        self.wait = WebDriverWait(self.driver, 10)

    def _save_cookies(self):
        os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
        with open(COOKIES_FILE, 'w') as f:
            json.dump(self.driver.get_cookies(), f)
        print("  - ℹ️  Куки сессии сохранены.")

    def _load_cookies(self):
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
            for cookie in cookies:
                self.driver.add_cookie(cookie)
            return True
        return False

    def login(self):
        try:
            self._initialize_driver()
            print("  - Пытаюсь войти с помощью сохраненных куки...")
            self.driver.get("https://hosting.timeweb.ru/")
            if self._load_cookies():
                self.driver.refresh()
                try:
                    self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a[href='/domains']")))
                    print("  - ✅ Вход по куки успешен!")
                    self.logged_in = True
                    return True
                except TimeoutException:
                    print("  - ❌ Вход по куки не удался. Выполняю стандартную авторизацию.")

            self.wait = WebDriverWait(self.driver, 30)
            print("  - Открываю страницу авторизации...")
            self.driver.get("https://hosting.timeweb.ru/")
            username_input = self.wait.until(EC.element_to_be_clickable((By.NAME, "username")))
            username_input.send_keys(self.config["timeweb_login"])
            self.driver.find_element(By.NAME, "password").send_keys(self.config["timeweb_password"])
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a[href='/domains']")))
            print("  - ✅ Успешная авторизация")
            self._save_cookies()
            self.logged_in = True
            return True

        except TimeoutException:
            print(f"  - ❌ Ошибка: Элемент не найден или страница не загрузилась вовремя.")
            screenshot_path = os.path.join(DATA_DIR, 'error_screenshot.png')
            self.driver.save_screenshot(screenshot_path)
            print(f"  - ℹ️  Скриншот сохранен для анализа.")
            return False
        except Exception as e:
            print(f"  - ❌ Произошла непредвиденная ошибка при авторизации: {e}")
            return False

    def update_a_records(self, new_ip):
        if not self.logged_in:
            print("  - ❌ Необходима авторизация для обновления записей.")
            return False

        all_successful = True
        for fqdn in self.config["domains"]:
            if not self.update_single_record(fqdn, new_ip):
                all_successful = False
        return all_successful

    def update_single_record(self, fqdn, new_ip):
        try:
            print(f"\n  - Обновление: {fqdn}")
            self._navigate_to_dns_page(fqdn)

            print(f"  - Ищу A-запись для '{fqdn}'...")
            xpath_row = f"//tr[td[1][normalize-space()='{fqdn}'] and td[2][normalize-space()='A']]"
            dns_row = self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath_row)))

            edit_button = dns_row.find_element(By.CSS_SELECTOR, "button.js-edit-record")
            edit_button.click()

            modal_xpath = "//div[contains(@class, 'k-window') and contains(., 'Редактировать A-запись')]"
            modal_window = self.wait.until(EC.visibility_of_element_located((By.XPATH, modal_xpath)))

            ip_input_xpath = ".//input[contains(@class, 'cpS-combobox-input') or (@name='value' and not(contains(@style,'display: none')))]"
            ip_input = modal_window.find_element(By.XPATH, ip_input_xpath)

            current_value = ip_input.get_attribute('value')
            if current_value == new_ip:
                print(f"  - ℹ️  IP-адрес для {fqdn} уже {new_ip}. Пропускаю.")
                cancel_button = modal_window.find_element(By.CSS_SELECTOR, "button.js-confirm-not")
                cancel_button.click()
                self.wait.until(EC.invisibility_of_element(cancel_button))
                return True

            ip_input.clear()
            ip_input.send_keys(new_ip)

            save_button = modal_window.find_element(By.CSS_SELECTOR, "button.js-confirm")
            save_button.click()
            self.wait.until(EC.invisibility_of_element(save_button))

            print(f"  - ✅ A-запись для {fqdn} обновлена на {new_ip}")
            time.sleep(1)
            return True

        except (TimeoutException, NoSuchElementException):
            print(f"  - ❌ Не удалось найти или изменить A-запись для '{fqdn}'.")
            screenshot_path = os.path.join(DATA_DIR, f'error_dns_{fqdn}.png')
            self.driver.save_screenshot(screenshot_path)
            print(f"  - ℹ️  Скриншот сохранен как {os.path.basename(screenshot_path)}")
            return False
        except Exception as e:
            print(f"  - ❌ Ошибка при обновлении {fqdn}: {e}")
            return False

    def get_a_records(self):
        if not self.logged_in:
            print("  - ❌ Необходима авторизация для получения записей.")
            return None

        records = {}
        print("\n  - Получаю текущие A-записи...")
        for fqdn in self.config["domains"]:
            try:
                self._navigate_to_dns_page(fqdn)

                xpath_row = f"//tr[td[1][normalize-space()='{fqdn}'] and td[2][normalize-space()='A']]"
                dns_row = self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath_row)))

                ip_address = dns_row.find_element(By.XPATH, "./td[3]").text.strip()
                records[fqdn] = ip_address
                print(f"  - Найдено: {fqdn} -> {ip_address}")

            except (TimeoutException, NoSuchElementException):
                print(f"  - ❌ Не удалось найти A-запись для '{fqdn}'.")
                records[fqdn] = "не найдена"

        return records

    def _navigate_to_dns_page(self, fqdn):
        parts = fqdn.split('.')
        is_subdomain = len(parts) > 2
        if is_subdomain:
            subdomain = parts[0]
            domain = ".".join(parts[1:])
            url = f"https://hosting.timeweb.ru/domains/dns-records/subdomain?fqdn={domain}&sub={subdomain}"
        else:
            domain = fqdn
            url = f"https://hosting.timeweb.ru/domains/dns-records/domain?fqdn={domain}"

        if self.driver.current_url != url:
            print(f"  - Перехожу на страницу DNS для {fqdn}")
            self.driver.get(url)

    def close(self):
        if self.driver:
            self.driver.quit()
            print("  - Браузер закрыт.")

def update_dns_records(config, new_ip):
    manager = TimeWebManager(config)
    try:
        if manager.login():
            return manager.update_a_records(new_ip)
        return False
    except Exception as e:
        print(f"  - ❌ Произошла критическая ошибка: {e}")
        return False
    finally:
        manager.close()


def get_dns_records(config):
    manager = TimeWebManager(config)
    try:
        if manager.login():
            return manager.get_a_records()
        return None
    except Exception as e:
        print(f"  - ❌ Произошла критическая ошибка: {e}")
        return None
    finally:
        manager.close()

def update_single_dns_record(config, fqdn, new_ip):
    manager = TimeWebManager(config)
    single_domain_config = config.copy()
    single_domain_config['domains'] = [fqdn]
    manager.config = single_domain_config

    try:
        if manager.login():
            return manager.update_a_records(new_ip)
        return False
    except Exception as e:
        print(f"  - ❌ Произошла критическая ошибка: {e}")
        return False
    finally:
        manager.close()