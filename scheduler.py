from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import subprocess
import logging
from datetime import datetime
import os
from wsgi import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)

def run_scrape():
    start_time = datetime.now()
    logging.info(f"Starting scraping job at {start_time}")
    try:
        # Use absolute path to ensure script is found
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        subprocess.run(["python", script_path], check=True)
        end_time = datetime.now()
        duration = end_time - start_time
        logging.info(f"Scraping job completed successfully. Duration: {duration}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Scraping job failed with error: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error in scraping job: {str(e)}")

if __name__ == "__main__":
    # Create scheduler
    scheduler = BackgroundScheduler()
    
    # Add job to run every hour
    scheduler.add_job(
        run_scrape,
        trigger=CronTrigger(hour='*'),  # Run every hour
        id='scrape_job',
        name='Scrape news articles every hour'
    )
    
    # Run scraping immediately
    run_scrape()
    
    # Start the scheduler
    scheduler.start()
    logging.info("Scheduler started")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=10000)

