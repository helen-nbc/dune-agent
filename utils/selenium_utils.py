from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import logging
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from utils.helper import generate_search_url




class SeleniumUtils:
    def __init__(self, user_agent: str = None):
        """Initialize SeleniumUtils with logging and WebDriver setup."""
        self._logger = logging.getLogger(self.__class__.__name__)
        self.driver = None
        self.set_driver(user_agent)

    def set_driver(self, user_agent: str = None):
        """Initialize Chrome WebDriver with necessary options."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Set a default user agent if not provided
        if not user_agent:
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.83 Safari/537.36"
        chrome_options.add_argument(f"user-agent={user_agent}")

        try:
            # Initialize WebDriver with ChromeDriverManager
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            self._logger.info("Chrome WebDriver has been successfully initialized.")
        except Exception as e:
            self._logger.error(f"Error initializing WebDriver: {e}")
            raise


    def get_queries_ids(self, input: str):
      """Extract query links from Dune Discover."""
      base_url = "https://dune.com/discover/content/relevant"
      input = {"q": input, "resource-type": "queries"}
      url = generate_search_url(base_url, input)

      if not self.driver:
          self._logger.error("WebDriver is not initialized.")
          return []

      queries_ids = []

      try:
          self.driver.get(url)
          WebDriverWait(self.driver, 10).until(
              EC.presence_of_element_located((By.TAG_NAME, "body"))
          )

          # Wait for the table with the class name styles_table__ro9iA to appearn
          try:
              table = WebDriverWait(self.driver, 10).until(
                  EC.presence_of_element_located((By.CLASS_NAME, "styles_table__ro9iA"))
              )
          except TimeoutException:
              self._logger.warning("No query table found.")
              return []

          # Get all the <a> tags inside the table
          links = table.find_elements(By.TAG_NAME, "a")


          for link in links:
              href = link.get_attribute("href")
              if href and href.startswith("https://dune.com/queries/"):
                  queries_ids.append(href)

          return queries_ids

      except Exception as e:
          self._logger.error(f"Error while scraping query links: {e}")
          return []


    def quit_driver(self):
        """Close the WebDriver session."""
        if self.driver:
            self.driver.quit()
            self._logger.info("WebDriver has been successfully closed.")
