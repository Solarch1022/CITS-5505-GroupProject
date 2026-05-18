import os
import sys
import time
import unittest
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import create_app
from models import User, Wallet, db


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")


class MarketplaceSeleniumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1440,1200")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")

        cls.driver = webdriver.Chrome(options=chrome_options)
        cls.wait = WebDriverWait(cls.driver, 10)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def unique_text(self, prefix):
        return f"{prefix}_{int(time.time() * 1000)}"

    def safe_click(self, element):
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            element
        )
        time.sleep(0.2)
        self.driver.execute_script("arguments[0].click();", element)

    def create_verified_user_for_browser_login(self):
        username = self.unique_text("seleniumuser")
        email = f"{username}@student.uwa.edu.au"
        password = "TestPass@123"

        app = create_app("development")
        with app.app_context():
            db.create_all()

            existing = User.query.filter_by(username=username).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()

            user = User(
                username=username,
                email=email,
                full_name="Selenium Test User",
                email_verified=True,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            db.session.add(Wallet(user_id=user.id, available_balance=100.0))
            db.session.commit()

        return username, password

    def test_home_page_and_browse_navigation(self):
        driver = self.driver

        driver.get(BASE_URL + "/")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        self.assertIn("UWA SecondHand", driver.page_source)
        self.assertIn("Marketplace statistics", driver.page_source)
        self.assertIn("Browse by category", driver.page_source)

        browse_link = driver.find_element(By.LINK_TEXT, "Browse")
        self.safe_click(browse_link)

        self.wait.until(EC.url_contains("/items"))
        self.assertIn("Browse listings", driver.page_source)

    def test_non_uwa_registration_is_rejected(self):
        driver = self.driver
        username = self.unique_text("outsider")

        driver.get(BASE_URL + "/register")
        self.wait.until(EC.presence_of_element_located((By.NAME, "username")))

        driver.find_element(By.NAME, "full_name").send_keys("Outside User")
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "email").send_keys(f"{username}@gmail.com")
        driver.find_element(By.NAME, "password").send_keys("TestPass@123")

        submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.safe_click(submit_button)

        self.wait.until(
            lambda d: "student.uwa.edu.au" in d.page_source or "UWA" in d.page_source
        )

        self.assertIn("/register", driver.current_url)
        self.assertIn("student.uwa.edu.au", driver.page_source)

    def test_verified_user_can_login_access_sell_and_logout(self):
        driver = self.driver
        username, password = self.create_verified_user_for_browser_login()

        driver.get(BASE_URL + "/login")
        self.wait.until(EC.presence_of_element_located((By.NAME, "username")))

        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)

        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.safe_click(login_button)

        self.wait.until(EC.url_contains("/dashboard"))
        self.assertIn(username, driver.page_source)

        driver.get(BASE_URL + "/sell")
        self.wait.until(EC.presence_of_element_located((By.ID, "sellItemForm")))

        self.assertIn("List a new item", driver.page_source)
        self.assertTrue(driver.find_element(By.NAME, "title").is_displayed())

        user_menu = driver.find_element(By.ID, "userMenuBtn")
        self.safe_click(user_menu)

        logout_button = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.dropdown-logout"))
        )
        self.safe_click(logout_button)

        self.wait.until(
            lambda d: d.current_url.rstrip("/") == BASE_URL.rstrip("/")
        )

        self.assertIn("Login", driver.page_source)
        self.assertIn("Register", driver.page_source)


if __name__ == "__main__":
    unittest.main()
