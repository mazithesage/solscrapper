from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
import time
import pandas as pd
from typing import Set, List, Optional
import re
import random
from datetime import datetime
import os
import argparse
import base58
from typing import Optional

class TransactionScraper:
    @staticmethod
    def is_valid_solana_address(address: str) -> bool:
        """Validate if a string is a valid Solana wallet address.
        
        Args:
            address: The string to validate
            
        Returns:
            bool: True if the address is valid, False otherwise
        """
        try:
            # Check basic string properties
            if not address or not isinstance(address, str):
                return False
                
            # Solana addresses are 32-44 characters long
            if not (32 <= len(address) <= 44):
                return False
                
            # Must only contain base58 characters
            if not all(c in '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz' for c in address):
                return False
                
            # Try to decode the base58 string
            decoded = base58.b58decode(address)
            
            # Solana addresses are 32 bytes after decoding
            if len(decoded) != 32:
                return False
                
            return True
        except Exception:
            return False
            
    def __init__(self, headless: bool = True):
        """Initialize the scraper
        
        Args:
            headless: Whether to run Chrome in headless mode
        """
        self.setup_driver(headless)
        self.base_url = "https://solscan.io/txs"
        self.wallet_addresses: Set[str] = set()
        self.output_dir = "scraped_data"
        os.makedirs(self.output_dir, exist_ok=True)
        self.page_size = 25  # Number of transactions per page
        self.rate_limit_delay = 3  # Base delay between requests in seconds
        self.rate_limit_jitter = 2  # Random jitter added to delay
        
    def setup_driver(self, headless: bool):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()
        
        # Run in non-headless mode for now to debug
        if headless:
            print("Running in non-headless mode for debugging")
        
        # Add common options for stability
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--enable-javascript")
        
        # Add user agent to avoid detection
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Additional preferences to avoid detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_settings.popups": 0,
            "download.prompt_for_download": False
        })
        
        try:
            # Use Selenium's built-in webdriver manager
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            
            # Execute CDP commands to modify navigator.webdriver flag
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            # Execute JavaScript to modify navigator properties
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            
            print(f"Successfully initialized Chrome driver with version {self.driver.capabilities['browserVersion']}")
            
        except Exception as e:
            print(f"Error details: {str(e)}")
            raise Exception(f"Failed to initialize Chrome driver. Make sure Chrome browser is installed.")
        
    def is_valid_solana_address(self, address: str) -> bool:
        """Check if a string is a valid Solana address"""
        if not address or len(address) < 32 or len(address) > 44:
            return False
        # Solana addresses are base58 encoded
        base58_pattern = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')
        return bool(base58_pattern.match(address))
    
    def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Add a random delay to avoid detection"""
        time.sleep(random.uniform(min_seconds, max_seconds))
        
    def wait_for_element(self, by: By, value: str, timeout: int = 10) -> Optional[bool]:
        """Wait for an element to be present and visible"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return bool(element)
        except TimeoutException:
            print(f"Timeout waiting for element: {value}")
            return None
        except Exception as e:
            print(f"Error waiting for element {value}: {e}")
            return None
        
    def wait_for_page_load(self, timeout: int = 30) -> bool:
        """Wait for the page to load completely"""
        try:
            # Wait for document ready state
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Wait for React to finish loading (check for root element)
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script(
                    "return document.querySelector('#__next') !== null"
                )
            )
            
            # Wait a bit for React to hydrate
            time.sleep(3)
            
            # Scroll down to trigger any lazy loading
            self.driver.execute_script("window.scrollTo(0, 300);")
            
            # Wait for network requests to complete
            time.sleep(2)
            
            return True
            
        except Exception as e:
            print(f"Error waiting for page load: {e}")
            return False
    
    def extract_addresses_from_page(self) -> Set[str]:
        """Extract wallet addresses from the current page"""
        addresses = set()
        
        try:
            # Wait for page to load completely
            if not self.wait_for_page_load():
                print("Page did not load completely")
                return addresses
            
            # Debug: Print page title and URL
            print(f"Current page title: {self.driver.title}")
            print(f"Current URL: {self.driver.current_url}")
            
            # Try different selectors for the transaction table
            table_selectors = [
                "table",  # Basic table element
                ".ant-table-wrapper",  # Ant Design table
                "[class*='table']",  # Any element with 'table' in its class
                "#transaction-list"  # Common ID for transaction lists
            ]
            
            table_element = None
            used_selector = None
            
            for selector in table_selectors:
                try:
                    print(f"Trying selector: {selector}")
                    table_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    used_selector = selector
                    print(f"Found table with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not table_element:
                print("Could not find transaction table with any selector")
                # Debug: Print page source
                print("Page source preview:")
                print(self.driver.page_source[:1000])
                return addresses
            
            # Get all rows directly using Selenium
            rows = table_element.find_elements(By.TAG_NAME, "tr")
            print(f"Found {len(rows)} rows using Selenium")
            
            # Process each row
            for row in rows:
                try:
                    # Get all links in the row
                    links = row.find_elements(By.TAG_NAME, "a")
                    print(f"Found {len(links)} links in row")
                    
                    for link in links:
                        try:
                            href = link.get_attribute("href") or ""
                            text = link.text.strip()
                            
                            print(f"Processing link: href={href}, text={text}")
                            
                            # Extract address from account links
                            if '/account/' in href:
                                address = href.split('/account/')[-1].split('?')[0]
                                if self.is_valid_solana_address(address):
                                    addresses.add(address)
                                    print(f"Found valid account address: {address}")
                            
                            # Extract addresses from transaction signatures
                            elif '/tx/' in href and self.is_valid_solana_address(text):
                                addresses.add(text)
                                print(f"Found valid transaction address: {text}")
                                
                        except Exception as e:
                            print(f"Error processing link: {e}")
                            continue
                            
                except Exception as e:
                    print(f"Error processing row: {e}")
                    continue
            
            if addresses:
                print(f"Extracted {len(addresses)} unique addresses from the current page")
            
        except Exception as e:
            print(f"Error extracting addresses from page: {e}")
            import traceback
            traceback.print_exc()
            
        return addresses
        
    def scrape_transactions(self, target_addresses: int = 1000, max_retries: int = 3) -> Set[str]:
        """Scrape wallet addresses from transactions until target count is reached
        
        Args:
            target_addresses: Number of unique addresses to collect (0 for unlimited)
            max_retries: Maximum number of retries per page
        """
        try:
            page = 1
            consecutive_empty_pages = 0
            max_empty_pages = 5  # Stop if we hit this many empty pages in a row
            
            while (target_addresses == 0 or len(self.wallet_addresses) < target_addresses) and consecutive_empty_pages < max_empty_pages:
                retry_count = 0
                success = False
                initial_count = len(self.wallet_addresses)
                
                while retry_count < max_retries and not success:
                    try:
                        # Calculate offset for pagination
                        offset = (page - 1) * self.page_size
                        page_url = f"{self.base_url}?cluster=mainnet&offset={offset}&limit={self.page_size}"
                        
                        remaining = target_addresses - len(self.wallet_addresses) if target_addresses > 0 else "unlimited"
                        print(f"Scraping page {page} (Remaining addresses needed: {remaining})")
                        print(f"Navigating to: {page_url}")
                        
                        # Load the page
                        self.driver.get(page_url)
                        self.random_delay(self.rate_limit_delay, self.rate_limit_delay + self.rate_limit_jitter)
                        
                        # Extract addresses
                        new_addresses = self.extract_addresses_from_page()
                        if new_addresses:
                            prev_count = len(self.wallet_addresses)
                            self.wallet_addresses.update(new_addresses)
                            new_count = len(self.wallet_addresses) - prev_count
                            print(f"Found {new_count} new addresses (Total: {len(self.wallet_addresses)})")
                            
                            # Save progress periodically
                            if page % 5 == 0:
                                self.save_progress()
                                
                            success = True
                            consecutive_empty_pages = 0 if new_count > 0 else consecutive_empty_pages + 1
                        else:
                            retry_count += 1
                            if retry_count < max_retries:
                                print(f"No addresses found. Retry {retry_count}/{max_retries}")
                                self.random_delay(5, 10)  # Longer delay on retry
                            else:
                                print(f"Failed to extract addresses after {max_retries} attempts")
                                consecutive_empty_pages += 1
                                
                    except WebDriverException as e:
                        print(f"WebDriver error: {e}")
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"Retrying... ({retry_count}/{max_retries})")
                            self.random_delay(5, 10)
                        else:
                            print(f"Failed after {max_retries} attempts")
                            consecutive_empty_pages += 1
                            
                    except Exception as e:
                        print(f"Unexpected error: {e}")
                        import traceback
                        traceback.print_exc()
                        break
                
                if consecutive_empty_pages >= max_empty_pages:
                    print(f"Stopping after {max_empty_pages} consecutive empty pages")
                    break
                    
                page += 1
                
                # Save progress after each page
                self.save_addresses()
                    
        except Exception as e:
            print(f"Error during scraping: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            self.save_addresses()
            self.driver.quit()
            
        return self.wallet_addresses
    
    def click_next_page(self) -> bool:
        """Click the next page button"""
        try:
            next_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "li.ant-pagination-next:not(.ant-pagination-disabled)"))
            )
            next_button.click()
            return True
        except Exception as e:
            print(f"Error clicking next page button: {e}")
            return False
    
    def save_progress(self):
        """Save current progress to a temporary file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.output_dir, f"addresses_progress_{timestamp}.csv")
        self.save_addresses(filename)
        
    def save_addresses(self, filename: str = None):
        """Save the scraped addresses to a CSV file"""
        if filename is None:
            filename = os.path.join(self.output_dir, "scraped_addresses.csv")
            
        df = pd.DataFrame(list(self.wallet_addresses), columns=['address'])
        df['timestamp'] = datetime.now().isoformat()
        df.to_csv(filename, index=False)
        print(f"Saved {len(self.wallet_addresses)} addresses to {filename}")
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.driver.quit()
        except Exception as e:
            print(f"Error during cleanup: {e}")

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Scrape Solana wallet addresses from Solscan')
    parser.add_argument('-n', '--num_addresses', type=int, default=1000,
                        help='Number of addresses to scrape (0 for unlimited)')
    parser.add_argument('--headless', action='store_true',
                        help='Run in headless mode (no browser window)')
    args = parser.parse_args()
    
    scraper = None
    try:
        print(f"Starting scraper to collect {args.num_addresses if args.num_addresses > 0 else 'unlimited'} addresses")
        print(f"Running in {'headless' if args.headless else 'visible'} mode")
        
        scraper = TransactionScraper(headless=args.headless)
        addresses = scraper.scrape_transactions(target_addresses=args.num_addresses)
        scraper.save_addresses()
        print(f"Scraping completed. Total unique addresses found: {len(addresses)}")
    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        if scraper:
            scraper.cleanup()

if __name__ == "__main__":
    main()
