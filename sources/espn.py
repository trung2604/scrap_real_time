import feedparser
from datetime import datetime
import logging

class EspnRssScraper:
    def __init__(self):
        self.source = "ESPN"
        self.rss_feeds = {
            "nba": "http://www.espn.com/espn/rss/nba/news",
            "soccer": "http://www.espn.com/espn/rss/soccer/news",
            "nfl": "http://www.espn.com/espn/rss/nfl/news",
            "mlb": "http://www.espn.com/espn/rss/mlb/news",
            "tennis": "http://www.espn.com/espn/rss/tennis/news",
            "golf": "http://www.espn.com/espn/rss/golf/news",
            "f1": "http://www.espn.com/espn/rss/f1/news",
            "olympics": "http://www.espn.com/espn/rss/olympics/news",
        }

    def scrape_all_articles(self):
        articles = []
        for category, rss_url in self.rss_feeds.items():
            logging.info(f"[ESPN RSS] Đang lấy tin từ: {rss_url}")
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                article = {
                    "title": entry.title,
                    "content": entry.summary if hasattr(entry, "summary") else "",
                    "url": entry.link,
                    "published_at": (
                        datetime(*entry.published_parsed[:6]).isoformat() + "Z"
                        if hasattr(entry, "published_parsed") and entry.published_parsed
                        else None
                    ),
                    "source": self.source,
                }
                articles.append(article)
        logging.info(f"[ESPN RSS] Tổng số bài lấy được: {len(articles)}")
        return articles

    def scrape_article_content(self, url):
        # Không cần thiết với RSS, nhưng giữ lại cho tương thích hệ thống
        return None

scraper = EspnRssScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper.scrape_article_content 