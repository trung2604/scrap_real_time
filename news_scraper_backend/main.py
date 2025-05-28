import json
import importlib
import logging
import signal
from database import save_article, get_last_scrape_time, update_scrape_time, get_scraping_stats
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
    # Scrape if last scrape was more than 15 minutes ago
    return datetime.utcnow() - last_scrape > timedelta(minutes=15)

def main():
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        config_path = Path(__file__).parent / "config.json"
        with open(config_path) as f:
            sources = json.load(f)

        stats_before = get_scraping_stats()
        logging.info("Starting scraping session...")
        logging.info(f"Current stats: {stats_before}")

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
                article_urls = module.scrape_all_articles(source["base_url"], source["article_url_pattern"])
                
                articles_saved = 0
                logging.info(f"Found {len(article_urls)} articles for {source['name']}")
                
                for url in article_urls:
                    if should_exit:
                        break

                    try:
                        article = module.scrape_article_content(url)
                        if article and save_article(article):
                            articles_saved += 1
                            if articles_saved % 10 == 0:
                                logging.info(f"Saved {articles_saved} articles from {source['name']}")
                    except Exception as e:
                        logging.error(f"Error scraping article {url}: {str(e)}")
                        continue

                update_scrape_time(source["name"])
                logging.info(f"Completed scraping {source['name']}. Saved {articles_saved} new articles.")
                        
            except Exception as e:
                logging.error(f"Error processing source {source['name']}: {str(e)}")
                continue

        stats_after = get_scraping_stats()
        logging.info("Scraping session completed")
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

