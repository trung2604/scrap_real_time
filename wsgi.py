from flask import Flask, jsonify
from database import get_db, get_scraping_stats
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('web.log'),
        logging.StreamHandler()
    ]
)

@app.route('/')
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/stats')
def get_stats():
    try:
        stats = get_scraping_stats()
        return jsonify(stats)
    except Exception as e:
        logging.error(f"Error getting stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000) 