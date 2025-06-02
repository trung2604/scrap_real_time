import json
import importlib
import logging
import signal
import sys
import time
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

        # Check existing articles
        logging.info("Checking existing articles in database...")
        existing_articles = check_existing_articles()

        stats_before = get_scraping_stats()
        logging.info("Starting scraping session...")
        logging.info(f"Current stats: {stats_before}")

        total_articles_saved = 0
        # Sort sources by last scrape time to prioritize sources that haven't been scraped recently
        sources.sort(key=lambda x: get_last_scrape_time(x["name"]) or datetime.min)

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
                # Get list of articles with retry logic
                max_retries = 3
                retry_delay = 5
                articles = None
                for attempt in range(max_retries):
                    try:
                        articles = module.scrape_all_articles()
                        if isinstance(articles, list):
                            break
                        logging.error(f"Expected list of articles from {source['name']}, got {type(articles)}")
                    except Exception as e:
                        logging.error(f"Error scraping {source['name']} (attempt {attempt + 1}/{max_retries}): {str(e)}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (attempt + 1))
                        continue

                if not articles:
                    logging.warning(f"No articles found for {source['name']}")
                    continue

                articles_saved = 0
                logging.info(f"Found {len(articles)} articles for {source['name']}")
                if articles:
                    logging.info(f"First article sample: {json.dumps(articles[0], default=str)}")

                # Save articles with rate limiting
                for article in articles:
                    if should_exit:
                        break
                    try:
                        if save_article(article):
                            articles_saved += 1
                            total_articles_saved += 1
                            logging.info(f"Saved article: {article.get('title', '')[:50]}...")
                        time.sleep(1)  # Rate limiting between saves
                    except Exception as e:
                        logging.error(f"Error saving article: {str(e)}")
                        continue

                # Update scrape time only if we successfully scraped and saved articles
                if articles_saved > 0:
                    update_scrape_time(source["name"])
                    logging.info(f"Completed scraping {source['name']}. Saved {articles_saved} new articles.")
                else:
                    logging.warning(f"No new articles saved for {source['name']}")

            except Exception as e:
                logging.error(f"Error processing source {source['name']}: {str(e)}")
                continue

    except Exception as e:
        logging.error(f"Error in main scraping loop: {str(e)}")
    finally:
        stats_after = get_scraping_stats()
        logging.info("Scraping session completed")
        logging.info(f"Total articles saved in this session: {total_articles_saved}")
        logging.info(f"Final stats: {stats_after}")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scraper.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    main()

