from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from contextlib import contextmanager
from dotenv import load_dotenv
import os
import logging
from datetime import datetime
import json

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_TIMEOUT = 5000  # 5 seconds timeout

@contextmanager
def get_db():
    client = None
    try:
        logging.info(f"Connecting to MongoDB at {MONGO_URI}")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=MONGO_TIMEOUT)
        # Test connection
        client.server_info()
        logging.info("Successfully connected to MongoDB")
        db = client["news_scraper"]
        yield db
    except ServerSelectionTimeoutError:
        logging.error(f"Database connection timeout after {MONGO_TIMEOUT}ms")
        raise
    except Exception as e:
        logging.error(f"Database error: {str(e)}")
        raise
    finally:
        if client:
            client.close()
            logging.info("MongoDB connection closed")

def check_existing_articles():
    with get_db() as db:
        try:
            articles = list(db.articles.find({}, {"url": 1, "title": 1, "published_at": 1, "source": 1}))
            logging.info(f"Found {len(articles)} articles in database")
            for article in articles:
                logging.info(f"Article: {article.get('title', 'no title')} "
                           f"from {article.get('source', 'no source')} "
                           f"published at {article.get('published_at', 'no date')} "
                           f"URL: {article.get('url', 'no url')}")
            return articles
        except Exception as e:
            logging.error(f"Error checking existing articles: {str(e)}")
            return []

def save_article(article):
    logging.info(f"Attempting to save article: {article.get('url', 'unknown URL')}")
    with get_db() as db:
        try:
            # Log article details
            logging.info(f"Article details: title='{article.get('title', 'no title')}', "
                        f"source='{article.get('source', 'no source')}', "
                        f"published_at='{article.get('published_at', 'no date')}', "
                        f"content_length={len(article.get('content', ''))}")
            
            # Check if article exists
            existing = db.articles.find_one({"url": article["url"]})
            if existing:
                logging.info(f"Article already exists in database: {article['url']}")
                logging.info(f"Existing article details: title='{existing.get('title', 'no title')}', "
                           f"published_at='{existing.get('published_at', 'no date')}', "
                           f"source='{existing.get('source', 'no source')}'")
                return False
                
            # Insert article
            logging.info("No existing article found, attempting to insert...")
            result = db.articles.insert_one(article)
            if result.inserted_id:
                logging.info(f"Successfully saved article with ID: {result.inserted_id}")
                # Verify the article was saved
                saved = db.articles.find_one({"_id": result.inserted_id})
                if saved:
                    logging.info(f"Verified article saved: {saved.get('title', 'no title')}")
                else:
                    logging.error("Article not found after saving!")
                return True
            else:
                logging.error("Failed to insert article - no ID returned")
                return False
                
        except Exception as e:
            logging.error(f"Error saving article: {str(e)}")
            logging.error(f"Article data: {json.dumps(article, default=str)}")
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
