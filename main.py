import json
import importlib
import logging
import signal
from database import save_article, get_last_scrape_time, update_scrape_time, get_scraping_stats, check_existing_articles
from pathlib import Path
from datetime import datetime, timedelta

# Global flag for graceful shutdown
should_exit = False

def signal_handler(signum, frame):
    global should_exit
    logging.info("Received shutdown signal, finishing current task...")
    should_exit = True

def should_scrape_source(source_name):
    last_scrape = get_last_scrape_time(source_name)
    if not last_scrape:
        return True
    # Scrape if last scrape was more than 1 minute ago (changed from 15 minutes for testing)
    return datetime.utcnow() - last_scrape > timedelta(minutes=1)

def main():
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        config_path = Path(__file__).parent / "config.json"
        with open(config_path) as f:
            sources = json.load(f)

        # Check existing articles
        logging.info("Checking existing articles in database...")
        existing_articles = check_existing_articles()

        stats_before = get_scraping_stats()
        logging.info("Starting scraping session...")
        logging.info(f"Current stats: {stats_before}")

        total_articles_saved = 0
        for source in sources:
            if should_exit:
                logging.info("Graceful shutdown initiated, exiting...")
                break

            if not should_scrape_source(source["name"]):
                logging.info(f"Skipping {source['name']} - recently scraped")
                continue

            try:
                logging.info(f"Starting scrape for {source['name']}")
                module = importlib.import_module(f"sources.{source['module']}")
                
                # Get list of articles
                articles = module.scrape_all_articles()
                if not isinstance(articles, list):
                    logging.error(f"Expected list of articles from {source['name']}, got {type(articles)}")
                    continue
                
                articles_saved = 0
                logging.info(f"Found {len(articles)} articles for {source['name']}")
                if articles:
                    logging.info(f"First article sample: {json.dumps(articles[0], default=str)}")
                
                for article in articles:
                    if should_exit:
                        break

                    if not isinstance(article, dict):
                        logging.error(f"Invalid article type: {type(article)}")
                        continue

                    # Log article data before saving
                    logging.info(f"Article data before saving: {json.dumps(article, default=str)}")

                    try:
                        logging.info(f"Attempting to save article: {article.get('url', 'unknown URL')}")
                        if save_article(article):
                            articles_saved += 1
                            total_articles_saved += 1
                            logging.info(f"Successfully saved article: {article.get('title', 'no title')}")
                            if articles_saved % 10 == 0:
                                logging.info(f"Saved {articles_saved} articles from {source['name']}")
                        else:
                            logging.warning(f"Failed to save article: {article.get('url', 'unknown URL')}")
                    except Exception as e:
                        logging.error(f"Error saving article {article.get('url', 'unknown URL')}: {str(e)}")
                        logging.error(f"Article data that caused error: {json.dumps(article, default=str)}")
                        continue

                update_scrape_time(source["name"])
                logging.info(f"Completed scraping {source['name']}. Saved {articles_saved} new articles.")
                        
            except Exception as e:
                logging.error(f"Error processing source {source['name']}: {str(e)}")
                continue

        stats_after = get_scraping_stats()
        logging.info("Scraping session completed")
        logging.info(f"Total articles saved in this session: {total_articles_saved}")
        logging.info(f"Final stats: {stats_after}")

    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scraper.log'),
            logging.StreamHandler()
        ]
    )
    main()

