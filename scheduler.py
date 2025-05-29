from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import subprocess
import logging
from datetime import datetime
from threading import Thread
from wsgi import app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)

scheduler = BackgroundScheduler()

@scheduler.scheduled_job(CronTrigger(minute='*/30'))  # Run every 30 minutes
def scrape_job():
    logging.info("Starting scheduled scraping job every 30 minutes...")
    try:
        subprocess.run(["python", "main.py"], check=True)
        logging.info("Scraping job completed successfully")
    except subprocess.CalledProcessError as e:
        logging.error(f"Scraping job failed with error: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error in scraping job: {str(e)}")

def run_scheduler():
    logging.info("⏰ Starting scheduler - sẽ chạy mỗi 30 phút...")
    try:
        scheduler.start()
        # Keep the main thread alive
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        logging.info("Scheduler stopped by user")
    except Exception as e:
        logging.error(f"Scheduler error: {str(e)}")
        raise

if __name__ == "__main__":
    # Start scheduler in a separate thread
    scheduler_thread = Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=10000)

