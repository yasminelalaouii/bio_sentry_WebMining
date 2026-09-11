import pymongo
import hashlib
from datetime import datetime
from config import MONGO_URI, MONGO_DATABASE, MONGO_COLLECTION, SCRAPING_SESSION


class MongoDBManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        self.connect()
    
    def connect(self):
        try:
            self.client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            self.db = self.client[MONGO_DATABASE]
            self.collection = self.db[MONGO_COLLECTION]
            self.collection.create_index([("post_id", 1), ("source", 1)], unique=True)
            print(f" Connecté à MongoDB: {MONGO_DATABASE}.{MONGO_COLLECTION}")
            return True
        except Exception as e:
            print(f" Erreur connexion MongoDB: {e}")
            return False
    
    def insert_post(self, post_data):
        try:
            post_data['date_scraped'] = datetime.utcnow()
            post_data['scraping_session'] = SCRAPING_SESSION
            
            if self.collection.find_one({
                "post_id": post_data['post_id'],
                "source": post_data['source']
            }):
                return False, "doublon"
            
            self.collection.insert_one(post_data)
            return True, "inséré"
        except pymongo.errors.DuplicateKeyError:
            return False, "doublon"
        except Exception as e:
            return False, f"erreur: {e}"
    
    def get_stats(self):
        return {
            "total_documents": self.collection.count_documents({}),
            "sources": list(self.collection.distinct("source")),
        }
    
    def close(self):
        if self.client:
            self.client.close()
            print(" Déconnecté de MongoDB")


def anonymize(text):
    if not text:
        return None
    return hashlib.sha256(str(text).encode()).hexdigest()[:16]