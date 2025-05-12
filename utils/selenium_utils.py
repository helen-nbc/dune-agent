from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import logging
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.service import Service as ChromiumService
from utils.helper import generate_search_url




class SeleniumUtils:
    def __init__(self, user_agent: str = None):
        """Initialize SeleniumUtils with logging and WebDriver setup."""
        self._logger = logging.getLogger(self.__class__.__name__)
        self.driver = None
        self.set_driver(user_agent)

    def set_driver(self, user_agent: str = None):
        """Initialize Chrome WebDriver with necessary options."""
        self._logger.info("Setting up Chrome WebDriver...")
        
        # Log system information for debugging
        import platform
        import os
        self._logger.info(f"Platform: {platform.platform()}")
        self._logger.info(f"Python version: {platform.python_version()}")
        
        # Check if chromium exists
        chromium_path = "/usr/bin/chromium"
        if os.path.exists(chromium_path):
            self._logger.info(f"Chromium found at {chromium_path}")
        else:
            self._logger.warning(f"Chromium not found at {chromium_path}")
            # Try to find chromium
            try:
                import subprocess
                result = subprocess.run(["which", "chromium"], capture_output=True, text=True)
                if result.stdout:
                    self._logger.info(f"Chromium found at: {result.stdout.strip()}")
                    chromium_path = result.stdout.strip()
                else:
                    self._logger.warning("Chromium not found in PATH")
            except Exception as e:
                self._logger.error(f"Error finding chromium: {e}")
        
        chrome_options = Options()
        # Essential options for running in container/headless environment
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless=new")  # Updated headless flag
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--remote-debugging-port=9222")
        
        # Set a default user agent if not provided
        if not user_agent:
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.83 Safari/537.36"
        chrome_options.add_argument(f"user-agent={user_agent}")
        
        # Log all chrome options for debugging
        self._logger.info(f"Chrome options: {chrome_options.arguments}")

        try:
            # FIXED: Correct way to initialize WebDriver with ChromeDriverManager
            # service = ChromiumService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
            # self._logger.info(f"ChromeDriver path: {service.path}")
            
            # Use the pre-installed ChromeDriver via apt
            chromedriver_path = "/usr/bin/chromedriver"
            self._logger.info(f"Using ChromeDriver at {chromedriver_path}")
             
            service = ChromiumService(executable_path=chromedriver_path)
            
            # Try with binary location explicitly set
            chrome_options.binary_location = chromium_path
            
            self.driver = webdriver.Chrome(
                service=service,
                options=chrome_options
            )
            self._logger.info("Chrome WebDriver has been successfully initialized.")
        except Exception as e:
            self._logger.error(f"Error initializing WebDriver: {e}")
            # More detailed error logging
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
            raise


    def get_queries_ids(self, input: str):
      """Extract query links from Dune Discover."""
      base_url = "https://dune.com/discover/content/relevant"
      input = {"q": input, "resource-type": "queries", "publicness": "public", "sort-by": "relevance"}
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
          # links = table.find_elements(By.TAG_NAME, "a")
          # Get all the <a> tags inside the table contain title 
          title_elements = table.find_elements(By.CLASS_NAME, "styles_title__54Ftn")


          for title_element in title_elements:
                try:
                    # Find the <a> tag that contains href
                    parent_link = title_element.find_element(By.XPATH, "./ancestor::a")
                    href = parent_link.get_attribute("href")
                    title = title_element.text if title_element else "Cannot find title"
                    # Only add if href is valid and related to Dune
                    if href and href.startswith("https://dune.com/queries"):
                        href = int(href.split("queries/")[-1])
                        queries_ids.append({"query_id": href, "title": title})
                except StaleElementReferenceException:
                    self._logger.warning("Stale element encountered, skipping.")
                    continue
                except Exception as e:
                    self._logger.error(f"Error processing link: {e}")
                    continue

          return queries_ids

      except Exception as e:
          self._logger.error(f"Error while scraping query links: {e}")
          return []


    def quit_driver(self):
        """Close the WebDriver session."""
        if self.driver:
            self.driver.quit()
            self._logger.info("WebDriver has been successfully closed.")
