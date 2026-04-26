"""
Wrapper around Selenium WebDriver for all browser-level operations.
All direct Selenium calls are encapsulated here.
"""

from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from backend.config import BROWSER_HEADLESS, ELEMENT_WAIT_TIMEOUT, PAGE_LOAD_TIMEOUT
from backend.logger import get_logger

logger = get_logger(__name__)


class BrowserWrapper:
    """Encapsulates all Selenium WebDriver interactions."""

    def __init__(self, headless: bool = BROWSER_HEADLESS):
        self._driver: Optional[webdriver.Chrome] = None
        self._headless = headless

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def launch(self) -> None:
        """Start a new Chrome browser session."""
        options = Options()
        if self._headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )

        service = Service(ChromeDriverManager().install())
        self._driver = webdriver.Chrome(service=service, options=options)
        self._driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        logger.info("Browser launched (headless=%s)", self._headless)

    def close(self) -> None:
        """Quit the browser and release resources."""
        if self._driver:
            self._driver.quit()
            self._driver = None
            logger.info("Browser closed")

    # ── Navigation ─────────────────────────────────────────────────────────────

    def open(self, url: str) -> None:
        """Navigate to *url*."""
        self._ensure_driver()
        logger.info("Navigating to %s", url)
        self._driver.get(url)

    def get_current_url(self) -> str:
        """Return the current page URL."""
        self._ensure_driver()
        return self._driver.current_url

    # ── Waiting ────────────────────────────────────────────────────────────────

    def wait_for_element(
        self,
        css_selector: str,
        timeout: int = ELEMENT_WAIT_TIMEOUT,
    ) -> WebElement:
        """Block until an element matching *css_selector* is present."""
        self._ensure_driver()
        wait = WebDriverWait(self._driver, timeout)
        return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css_selector)))

    def wait_for_all_elements(
        self,
        css_selector: str,
        timeout: int = ELEMENT_WAIT_TIMEOUT,
    ) -> list[WebElement]:
        """Block until at least one element matching *css_selector* is present, then return all."""
        self._ensure_driver()
        wait = WebDriverWait(self._driver, timeout)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css_selector)))
        return self._driver.find_elements(By.CSS_SELECTOR, css_selector)

    # ── Element Interaction ────────────────────────────────────────────────────

    def click(self, css_selector: str, timeout: int = ELEMENT_WAIT_TIMEOUT) -> None:
        """Wait for and click an element."""
        element = self.wait_for_element(css_selector, timeout)
        element.click()
        logger.debug("Clicked element: %s", css_selector)

    def get_text(self, css_selector: str, timeout: int = ELEMENT_WAIT_TIMEOUT) -> str:
        """Wait for an element and return its trimmed text content."""
        element = self.wait_for_element(css_selector, timeout)
        return element.text.strip()

    def get_attribute(
        self,
        css_selector: str,
        attribute: str,
        timeout: int = ELEMENT_WAIT_TIMEOUT,
    ) -> Optional[str]:
        """Wait for an element and return the value of *attribute*."""
        element = self.wait_for_element(css_selector, timeout)
        return element.get_attribute(attribute)

    # ── Page Source ────────────────────────────────────────────────────────────

    def get_page_source(self) -> str:
        """Return the full HTML source of the current page."""
        self._ensure_driver()
        return self._driver.page_source

    # ── Internals ──────────────────────────────────────────────────────────────

    def _ensure_driver(self) -> None:
        if self._driver is None:
            raise RuntimeError("Browser not launched. Call launch() first.")

    # ── Context Manager ────────────────────────────────────────────────────────

    def __enter__(self):
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
