from datetime import datetime
import logging
from newspaper import Article
import dateutil.parser
import json
import time
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.append(str(Path(__file__).parent.parent))
from utils import fetch_url

class BaseScraper:
    def __init__(self, source_name, base_url, article_url_pattern):
        self.source_name = source_name
        self.base_url = base_url
        self.article_url_pattern = article_url_pattern
        self.max_links_to_crawl = 100

    def _get_soup(self, url):
        """Get BeautifulSoup object for URL"""
        return fetch_url(url)

    def _extract_with_newspaper(self, url):
        """Extract article using newspaper3k"""
        try:
            article = Article(url)
            article.download()
            article.parse()
            return {
                'title': article.title,
                'text': article.text,
                'publish_date': article.publish_date
            }
        except Exception as e:
            logging.error(f"[{self.source_name}] Newspaper3k error for {url}: {e}")
            return None

    def _extract_date_from_url(self, url):
        """Extract date from URL if possible"""
        import re
        try:
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            if date_match:
                year, month, day = date_match.groups()
                return dateutil.parser.parse(f"{year}-{month}-{day}")
            return None
        except Exception as e:
            logging.error(f"[{self.source_name}] Error extracting date from URL: {e}")
            return None

    def _extract_date_from_meta(self, soup):
        """Extract date from meta tags"""
        meta_tags = [
            ('meta', {'property': 'article:published_time'}),
            ('meta', {'name': 'pubdate'}),
            ('meta', {'property': 'og:published_time'}),
            ('meta', {'name': 'date'})
        ]
        for tag, attrs in meta_tags:
            meta = soup.find(tag, attrs)
            if meta and meta.get('content'):
                try:
                    return dateutil.parser.parse(meta['content'])
                except Exception:
                    continue
        return None

    def _extract_date_from_jsonld(self, soup):
        """Extract date from JSON-LD"""
        try:
            scripts = soup.find_all('script', {'type': 'application/ld+json'})
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        for field in ['datePublished', 'dateCreated']:
                            if field in data:
                                return dateutil.parser.parse(data[field])
                except Exception:
                    continue
            return None
        except Exception:
            return None

    def scrape_article_content(self, url):
        """Default implementation to scrape article content"""
        try:
            time.sleep(2)  # Rate limiting
            
            # Try newspaper3k first
            result = self._extract_with_newspaper(url)
            if result and result.get('title') and result.get('text'):
                title = result['title']
                content = result['text']
                published_at = result.get('publish_date')
                
                if not published_at:
                    published_at = self._extract_date_from_url(url)
                    if not published_at:
                        soup = self._get_soup(url)
                        if soup:
                            published_at = self._extract_date_from_meta(soup)
                            if not published_at:
                                published_at = self._extract_date_from_jsonld(soup)

                if title and content and published_at:
                    return {
                        "title": title.strip(),
                        "url": url,
                        "source": self.source_name,
                        "content": content.strip(),
                        "published_at": published_at,
                        "scraped_at": datetime.utcnow()
                    }

            return None

        except Exception as e:
            logging.error(f"[{self.source_name}] Error scraping article {url}: {str(e)}")
            return None

    def scrape_all_articles(self):
        """Method to be implemented by child classes"""
        raise NotImplementedError("Subclasses must implement scrape_all_articles()")

