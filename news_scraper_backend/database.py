from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from contextlib import contextmanager
from dotenv import load_dotenv
import os
import logging
from datetime import datetime

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_TIMEOUT = 5000  # 5 seconds timeout

@contextmanager
def get_db():
    client = None
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=MONGO_TIMEOUT)
        # Test connection
        client.server_info()
        db = client["news_scraper"]
        yield db
    except ServerSelectionTimeoutError:
        logging.error("Database connection timeout")
        raise
    except Exception as e:
        logging.error(f"Database error: {str(e)}")
        raise
    finally:
        if client:
            client.close()

def save_article(article):
    with get_db() as db:
        try:
            if not db.articles.find_one({"url": article["url"]}):
                db.articles.insert_one(article)
                return True
            return False
        except Exception as e:
            logging.error(f"Error saving article: {str(e)}")
            return False

def get_last_scrape_time(source_name):
    with get_db() as db:
        try:
            status = db.scraping_status.find_one({"source": source_name})
            return status["last_scrape"] if status else None
        except Exception as e:
            logging.error(f"Error getting last scrape time: {str(e)}")
            return None

def update_scrape_time(source_name):
    with get_db() as db:
        try:
            db.scraping_status.update_one(
                {"source": source_name},
                {"$set": {"source": source_name, "last_scrape": datetime.utcnow()}},
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"Error updating scrape time: {str(e)}")
            return False

def get_scraping_stats():
    with get_db() as db:
        try:
            stats = {
                "total_articles": db.articles.count_documents({}),
                "sources": {}
            }
            for source in db.scraping_status.find():
                stats["sources"][source["source"]] = {
                    "last_scrape": source["last_scrape"],
                    "article_count": db.articles.count_documents({"source": source["source"]})
                }
            return stats
        except Exception as e:
            logging.error(f"Error getting scraping stats: {str(e)}")
            return None
