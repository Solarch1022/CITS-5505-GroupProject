import os
import time
import unittest

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait,Select
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

    def create_listing(
            self, 
            title=None, 
            description="A working item for Selenium listing tests on the UWA marketplace", 
            price="25",
            category="Electronics",
            condition="Good"
        ):
        driver = self.driver
        wait = self.wait

        title = title or self.unique_text("Listing")

        driver.get(f"{BASE_URL}/sell")

        wait.until(EC.presence_of_element_located((By.NAME, "title")))

        driver.find_element(By.NAME, "title").send_keys(title)
        driver.find_element(By.NAME, "description").send_keys(description)
        driver.find_element(By.NAME, "price").send_keys(price)

        Select(driver.find_element(By.NAME, "category")).select_by_visible_text(category)
        Select(driver.find_element(By.NAME, "condition")).select_by_visible_text(condition)

        publish_button = wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "button[name='intent'][value='publish'], input[name='intent'][value='publish']"
            ))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", publish_button)
        driver.execute_script("arguments[0].click();", publish_button)

        try:
            wait.until(EC.url_contains("/item/"))
        except Exception:
            print("Current URL after submit:", driver.current_url)
            print(driver.page_source[:2000])
        return title
    
    def create_draft(
            self,
            title=None,
            description="Need to double-check a few details before publishing this draft listing.",
    ):
        driver = self.driver
        wait = self.wait

        title = title or self.unique_text("draft")

        driver.get(f"{BASE_URL}/sell")
        wait.until(EC.presence_of_element_located((By.NAME, "title")))

        title_input = driver.find_element(By.NAME, "title")
        description_input = driver.find_element(By.NAME, "description")

        title_input.send_keys(title)
        description_input.send_keys(description)

        form = title_input.find_element(By.XPATH, "./ancestor::form")

        driver.execute_script("""
            const form = arguments[0];
            let intentInput = form.querySelector('input[name="intent"]');
            if (!intentInput) {
                intentInput = document.createElement('input');
                intentInput.type = 'hidden';
                intentInput.name = 'intent';
                form.appendChild(intentInput);
            }
            intentInput.value = 'draft';
            form.submit();
        """, form)

        wait.until(EC.url_contains("/dashboard"))
        return title
    
    def test_save_draft_and_hide_it_from_public_browse(self):
        username, _, password = self.register_user()
        self.login_user(username, password)

        draft_title = self.create_draft()

        self.assertIn("/dashboard", self.driver.current_url)
        self.assertIn(draft_title, self.driver.page_source)

        self.driver.get(f"{BASE_URL}/browse")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        self.assertNotIn(draft_title, self.driver.page_source)

    def test_create_listing_and_see_it_in_browse(self):
        username, _, password = self.register_user()
        self.login_user(username, password)

        listing_title = self.create_listing()

        self.assertIn("/item/", self.driver.current_url)
        self.assertIn(listing_title, self.driver.page_source)

        self.driver.get(f"{BASE_URL}/browse")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        self.assertIn(listing_title, self.driver.page_source)

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