import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB
MONGO_URI = "mongodb+srv://hajartaghi555_db_user:fFjWeAl3tyfb1FAd@hajar.qbnutif.mongodb.net/?appName=Hajar"
MONGO_DATABASE = "bio_sentry"
MONGO_COLLECTION = "raw_scraped" # I change the names after each extraction step 

# Selenium / Chrome
CHROME_OPTIONS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--window-size=1440,900",
    "--lang=en-US",
    "--disable-blink-features=AutomationControlled",
]

# Sources
REDDIT_SUBREDDITS = ["AskDocs", "medicine", "sideeffects", "pharmacology"]
REDDIT_KEYWORDS = ["side effects", "medication", "drug reaction", "adverse effect"]

# Timing 
MIN_DELAY = 2.5
MAX_DELAY = 5.5
PAGE_LOAD_TIMEOUT = 30

# Scraping session
from datetime import datetime
SCRAPING_SESSION = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"