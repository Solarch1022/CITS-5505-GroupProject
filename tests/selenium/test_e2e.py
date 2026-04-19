import os
import time
import unittest

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")


class MarketplaceSeleniumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = webdriver.ChromeOptions()
        cls.driver = webdriver.Chrome(options=options)
        cls.wait = WebDriverWait(cls.driver, 10)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def setUp(self):
        self.driver.get(BASE_URL)
        self.driver.delete_all_cookies()
        self.driver.execute_script("window.localStorage.clear();")
        self.driver.execute_script("window.sessionStorage.clear();")

    def unique_text(self, prefix: str) -> str:
        return f"{prefix}_{int(time.time() * 1000)}"

    def register_user(
        self,
        username=None,
        email=None,
        password="testpass123",
        full_name="Selenium User"
    ):
        driver = self.driver
        wait = self.wait

        username = username or self.unique_text("user")
        email = email or f"{username}@student.uwa.edu.au"

        driver.get(f"{BASE_URL}/register")

        wait.until(EC.presence_of_element_located((By.NAME, "username")))

        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "email").send_keys(email)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.NAME, "full_name").send_keys(full_name)

        driver.find_element(By.CSS_SELECTOR, "form button[type='submit']").click()

        wait.until(EC.url_contains("/login"))
        return username, email, password

    def login_user(self, username, password="testpass123"):
        driver = self.driver
        wait = self.wait

        driver.get(f"{BASE_URL}/login")

        wait.until(EC.presence_of_element_located((By.NAME, "username")))

        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, "form button[type='submit']").click()

        wait.until(EC.url_contains("/dashboard"))

    def test_register_with_valid_uwa_email(self):
        username, _, _ = self.register_user()
        self.assertIn("/login", self.driver.current_url)

    def test_register_with_non_uwa_email_fails(self):
        driver = self.driver
        wait = self.wait

        bad_username = self.unique_text("baduser")
        driver.get(f"{BASE_URL}/register")

        wait.until(EC.presence_of_element_located((By.NAME, "username")))

        driver.find_element(By.NAME, "username").send_keys(bad_username)
        driver.find_element(By.NAME, "email").send_keys(f"{bad_username}@gmail.com")
        driver.find_element(By.NAME, "password").send_keys("testpass123")
        driver.find_element(By.NAME, "full_name").send_keys("Bad User")
        driver.find_element(By.CSS_SELECTOR, "form button[type='submit']").click()

        self.assertIn("/register", self.driver.current_url)
        self.assertIn("@student.uwa.edu.au", self.driver.page_source)

    def test_login_and_logout_flow(self):
        username, _, password = self.register_user()
        self.login_user(username, password)

        self.assertIn("/dashboard", self.driver.current_url)

        logout_button = self.driver.find_element(
            By.CSS_SELECTOR,
            "form[action$='/logout'] button[type='submit']"
        )
        logout_button.click()

        self.wait.until(EC.url_to_be(f"{BASE_URL}/"))
        self.assertEqual(f"{BASE_URL}/", self.driver.current_url)


if __name__ == "__main__":
    unittest.main()