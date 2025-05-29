from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import subprocess
import logging
from datetime import datetime
from threading import Thread
from wsgi import app
import os

# Configure logging
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
        # Use absolute path to ensure script is found
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        subprocess.run(["python", script_path], check=True)
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
    
    # In production (Render), use gunicorn
    if os.environ.get('RENDER'):
        import gunicorn.app.base

        class StandaloneApplication(gunicorn.app.base.BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    self.cfg.set(key, value)

            def load(self):
                return self.application

        options = {
            'bind': '0.0.0.0:10000',
            'workers': 1,
            'timeout': 120
        }
        StandaloneApplication(app, options).run()
    else:
        # In development, use Flask's built-in server
        app.run(host='0.0.0.0', port=10000)

