# reddit_rss_scraper.py

import requests
import pymongo
import time
from datetime import datetime


MONGO_URI = "mongodb+srv://hajartaghi555_db_user:fFjWeAl3tyfb1FAd@hajar.qbnutif.mongodb.net/?appName=Hajar"
client     = pymongo.MongoClient(MONGO_URI)
db         = client["bio_sentry"]
collection = db["raw_reddit"]


SUBREDDITS = ["AskDocs", "medicine", "sideeffects", "pharmacology"]
KEYWORDS = ["side effects", "medication", "drug reaction", "adverse effect"]

HEADERS = {"User-Agent": "BioSentryBot/1.0"}

def scrape_reddit_rss():
    total = 0

    for subreddit in SUBREDDITS:
        for keyword in KEYWORDS:
            # URL RSS de recherche Reddit
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
            params = {
                "q": keyword,
                "restrict_sr": 1,
                "sort": "new",
                "limit": 100,
                "t": "year"
            }

            try:
                response = requests.get(url, headers=HEADERS,
                                        params=params, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    posts = data["data"]["children"]

                    for post in posts:
                        p = post["data"]

                        if collection.find_one({"post_id": p["id"]}):
                            continue

                        collection.insert_one({
                            "source": "reddit_rss",
                            "subreddit": subreddit,
                            "post_id": p["id"],
                            "title": p["title"],
                            "text": p.get("selftext", ""),
                            "score": p["score"],
                            "num_comments": p["num_comments"],
                            "created_utc": p["created_utc"],
                            "date_scraped": datetime.utcnow(),
                            "search_query": keyword,
                            "url": f"https://reddit.com{p['permalink']}"
                        })
                        total += 1

                    print(f"   r/{subreddit} + '{keyword}' → {len(posts)} posts")

                elif response.status_code == 429:
                    print("  Rate limit — pause 60s")
                    time.sleep(60)

            except Exception as e:
                print(f"  Erreur: {e}")

            time.sleep(3)  # Pause polie entre chaque requête

    print(f"\n Total: {total} posts sauvegardés")

scrape_reddit_rss()