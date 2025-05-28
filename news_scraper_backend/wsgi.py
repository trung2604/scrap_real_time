from flask import Flask
from database import get_scraping_stats

app = Flask(__name__)

@app.route('/')
def health_check():
    stats = get_scraping_stats()
    if stats:
        return {
            "status": "healthy",
            "stats": stats
        }, 200
    return {"status": "unhealthy"}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000) 