from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import requests
from bs4 import BeautifulSoup
import os
import time
import logging
from tqdm import tqdm
import urllib.parse
import re

# Set up logging
logging.basicConfig(filename='lummi_scraper.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
DOWNLOAD_FOLDER = "lummi_images"
MAX_IMAGES = 50  # Maximum number of images to download (configurable)
SCROLL_PAUSE = 2  # Seconds to wait after each scroll
REQUEST_DELAY = 0.5  # Seconds between download requests
RETRY_ATTEMPTS = 3  # Number of retries for failed downloads
HEADLESS = True  # Run browser in headless mode

def setup_driver(browser='chrome'):
    """Set up Selenium WebDriver with headless option."""
    if browser.lower() == 'chrome':
        options = Options()
        if HEADLESS:
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(options=options)
    elif browser.lower() == 'firefox':
        options = webdriver.FirefoxOptions()
        if HEADLESS:
            options.add_argument('--headless')
        driver = webdriver.Firefox(options=options)
    else:
        raise ValueError("Unsupported browser. Use 'chrome' or 'firefox'.")
    return driver

def clean_filename(name):
    """Sanitize filename to remove invalid characters."""
    return re.sub(r'[^\w\s.-]', '', name.replace(' ', '_').lower())[:50]

def download_image(url, folder, filename, session):
    """Download an image with retries."""
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = session.get(url, stream=True, timeout=10)
            if response.status_code == 200:
                file_path = os.path.join(folder, filename)
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                logging.info(f"Downloaded: {file_path}")
                return True
            else:
                logging.warning(f"Failed to download {url}: Status {response.status_code}")
        except Exception as e:
            logging.error(f"Error downloading {url}: {e}")
        time.sleep(REQUEST_DELAY)
    return False

def main():
    # User inputs
    prompt = input("Enter your search prompt: ")
    max_images = int(input(f"Enter max number of images to download (default {MAX_IMAGES}): ") or MAX_IMAGES)
    browser = input("Enter browser (chrome/firefox, default chrome): ") or 'chrome'
    
    # Create download folder
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    
    # Set up requests session with user-agent
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    # Set up WebDriver
    driver = setup_driver(browser)
    try:
        # Navigate to Lummi.ai
        driver.get("https://www.lummi.ai")
        logging.info("Navigated to Lummi.ai")
        time.sleep(2)  # Wait for page load

        # Find and fill search bar (adjust selector based on Lummi.ai's HTML)
        try:
            search_bar = driver.find_element(By.CSS_SELECTOR, "input[placeholder*='Search']")  # Update selector
            search_bar.send_keys(prompt)
            search_bar.send_keys(Keys.RETURN)
            logging.info(f"Submitted search for: {prompt}")
            time.sleep(3)  # Wait for results
        except Exception as e:
            logging.error(f"Search bar error: {e}")
            print("Could not find search bar. Please check the CSS selector.")
            return

        # Scroll to load all images
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        logging.info("Finished scrolling to load images")

        # Parse page for images
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        img_tags = soup.find_all('img')
        downloaded = 0

        print(f"Found {len(img_tags)} images. Downloading up to {max_images}...")
        for img in tqdm(img_tags, desc="Downloading images"):
            if downloaded >= max_images:
                break
            src = img.get('src')
            if not src or 'http' not in src:
                continue

            # Try to get higher resolution (e.g., from 'data-fullsrc' or download link)
            full_src = img.get('data-fullsrc') or src  # Adjust attribute based on inspection
            title = img.get('alt') or f"image_{downloaded}"
            filename = clean_filename(f"{title}.jpg")

            if download_image(full_src, DOWNLOAD_FOLDER, filename, session):
                downloaded += 1

        print(f"Downloaded {downloaded} images to {DOWNLOAD_FOLDER}")
        logging.info(f"Completed: Downloaded {downloaded} images for prompt '{prompt}'")

    finally:
        driver.quit()
        session.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Script failed: {e}")
        print(f"An error occurred: {e}. Check lummi_scraper.log for details.")