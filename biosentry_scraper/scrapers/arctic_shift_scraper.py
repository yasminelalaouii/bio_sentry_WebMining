import requests
import pymongo
from datetime import datetime
import time

#  Connexion MongoDB Atlas
MONGO_URI = "mongodb+srv://hajartaghi555_db_user:fFjWeAl3tyfb1FAd@hajar.qbnutif.mongodb.net/?appName=Hajar"

client     = pymongo.MongoClient(MONGO_URI)
db         = client["bio_sentry"]
collection = db["raw_reddit"]

SUBREDDITS = ["AskDocs", "medicine", "sideeffects", "pharmacology"]
KEYWORDS = ["side effects", "medication reaction", "adverse effect",
            "after taking", "drug reaction"]

def scrape_arctic_shift():
    print("\n Arctic Shift — Archive Reddit (Sans compte)")
    base_url = "https://arctic-shift.photon-reddit.com/api/posts/search"
    total = 0

    for subreddit in SUBREDDITS:
        for keyword in KEYWORDS:
            params = {
                "subreddit": subreddit,
                "query": keyword,
                "limit": 100,
                "sort": "desc"
            }

            try:
                response = requests.get(base_url, params=params, timeout=15)

                if response.status_code == 200:
                    posts = response.json().get("data", [])

                    for post in posts:
                        if collection.find_one({"post_id": post.get("id")}):
                            continue

                        collection.insert_one({
                            "source": "arctic_shift",
                            "subreddit": subreddit,
                            "post_id": post.get("id"),
                            "title": post.get("title", ""),
                            "text": post.get("selftext", ""),
                            "score": post.get("score", 0),
                            "created_utc": post.get("created_utc"),
                            "date_scraped": datetime.utcnow(),
                            "search_query": keyword
                        })
                        total += 1

                    print(f"   r/{subreddit} + '{keyword}' → {len(posts)} posts")

                time.sleep(2)

            except Exception as e:
                print(f"   Erreur: {e}")

    print(f"\n   Total: {total} posts sauvegardés")

scrape_arctic_shift()