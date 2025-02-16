from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import pandas as pd
from typing import Set, List, Optional
import re
import random
from datetime import datetime
import os

class TransactionScraper:
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
        
    def setup_driver(self, headless: bool):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")  # Updated headless mode syntax
        
        # Add common options for stability
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        
        # Add user agent to avoid detection
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            # Use ChromeDriverManager with specific OS and architecture settings
            manager = ChromeDriverManager()
            driver_path = manager.install()
            
            # Create service with the installed driver
            service = Service(executable_path=driver_path)
            
            # Initialize the driver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(30)
            
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
        
    def extract_addresses_from_page(self) -> Set[str]:
        """Extract wallet addresses from the current page"""
        addresses = set()
        
        # Wait for the transaction table to load
        if not self.wait_for_element(By.CLASS_NAME, "ant-table-tbody"):
            return addresses
            
        try:
            # Get the page source and parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Find the transaction table
            table = soup.find('div', class_='ant-table-content')
            if not table:
                print("Transaction table not found")
                return addresses
            
            # Extract addresses from table rows
            for row in table.find_all('tr', class_='ant-table-row'):
                # Look for account links
                for link in row.find_all('a'):
                    href = link.get('href', '')
                    text = link.get_text().strip()
                    
                    # Extract address from account links
                    if '/account/' in href:
                        address = href.split('/account/')[-1].split('?')[0]
                        if self.is_valid_solana_address(address):
                            addresses.add(address)
                    
                    # Extract addresses from transaction signatures
                    elif '/tx/' in href and self.is_valid_solana_address(text):
                        addresses.add(text)
                        
        except Exception as e:
            print(f"Error extracting addresses from page: {e}")
            
        return addresses
        
    def scrape_transactions(self, num_pages: int = 5, max_retries: int = 3) -> Set[str]:
        """Scrape wallet addresses from multiple pages of transactions"""
        retry_count = 0
        current_page = 1
        
        while current_page <= num_pages and retry_count < max_retries:
            try:
                # Load the page
                if current_page == 1:
                    self.driver.get(self.base_url)
                
                print(f"Scraping page {current_page}/{num_pages}")
                self.random_delay(2, 4)
                
                # Extract addresses
                new_addresses = self.extract_addresses_from_page()
                if new_addresses:
                    self.wallet_addresses.update(new_addresses)
                    print(f"Found {len(new_addresses)} new addresses (Total: {len(self.wallet_addresses)})")
                    
                    # Save progress periodically
                    if current_page % 5 == 0:
                        self.save_progress()
                    
                    # Move to next page if not on last page
                    if current_page < num_pages:
                        if not self.click_next_page():
                            print("Could not navigate to next page")
                            break
                    
                    current_page += 1
                    retry_count = 0  # Reset retry count on successful scrape
                else:
                    retry_count += 1
                    print(f"No addresses found on page {current_page}. Retry {retry_count}/{max_retries}")
                    self.random_delay(5, 10)  # Longer delay on retry
                    
            except WebDriverException as e:
                print(f"WebDriver error: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"Retrying... ({retry_count}/{max_retries})")
                    self.random_delay(5, 10)
                    continue
                break
                
            except Exception as e:
                print(f"Unexpected error: {e}")
                break
                
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
    scraper = None
    try:
        scraper = TransactionScraper(headless=True)
        addresses = scraper.scrape_transactions(num_pages=5)
        scraper.save_addresses()
        print(f"Scraping completed. Total unique addresses found: {len(addresses)}")
    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        if scraper:
            scraper.cleanup()

if __name__ == "__main__":
    main()
