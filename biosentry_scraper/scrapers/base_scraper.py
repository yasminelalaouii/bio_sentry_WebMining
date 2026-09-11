import os
import time
import random
import socket
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc

from config import CHROME_OPTIONS, MIN_DELAY, MAX_DELAY, PAGE_LOAD_TIMEOUT


class BaseSeleniumScraper:
    def __init__(self):
        self.driver = None
        self.create_driver()
    
    def create_driver(self):
        options = uc.ChromeOptions()
        for opt in CHROME_OPTIONS:
            options.add_argument(opt)
        
        home = os.environ.get('USERPROFILE', os.path.expanduser('~'))
        candidate_paths = [
            os.path.join(home, r".wdm\drivers\chromedriver\win64\147.0.7727.117\chromedriver-win32\chromedriver.exe"),
            os.path.join(home, "appdata", "roaming", "undetected_chromedriver", "chromedriver.exe"),
        ]
        driver_path = next((p for p in candidate_paths if os.path.exists(p)), None)
        
        socket.setdefaulttimeout(120)
        
        for attempt in range(3):
            try:
                print(f"  -> Lancement Chrome (tentative {attempt+1}/3)...")
                self.driver = uc.Chrome(
                    options=options,
                    driver_executable_path=driver_path,
                    version_main=147
                )
                self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                print("  -> Chrome lancé !")
                return
            except Exception as e:
                print(f"  Erreur: {e}")
                time.sleep(15)
        
        raise RuntimeError("Impossible de lancer Chrome")
    
    def safe_get(self, url, wait_selector="body", timeout=30):
        try:
            self.driver.get(url)
        except Exception:
            pass
        
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
            return True
        except TimeoutException:
            return False
    
    def delay(self, min_s=MIN_DELAY, max_s=MAX_DELAY):
        """Délai aléatoire anti-détection"""
        time.sleep(random.uniform(min_s, max_s))
    
    def scroll_page(self, max_y=3000, step=600):
        """Scroll progressif pour lazy loading"""
        try:
            for y in range(step, max_y + step, step):
                self.driver.execute_script(f"window.scrollTo(0, {y});")
                time.sleep(random.uniform(0.5, 1.0))
        except Exception:
            pass
    
    def close_popups(self):
        """Ferme les pop-ups courantes"""
        xpaths = [
            "//button[contains(@aria-label,'Close')]",
            "//button[contains(text(),'Close')]",
            "//button[contains(text(),'No thanks')]",
            "//button[contains(text(),'Accept')]",
            "//button[contains(text(),'Got it')]",
        ]
        for xpath in xpaths:
            try:
                self.driver.find_element(By.XPATH, xpath).click()
                self.delay(0.5, 1)
            except Exception:
                pass
    
    def quit(self):
        """Ferme le driver"""
        if self.driver:
            self.driver.quit()