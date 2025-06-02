from datetime import datetime, timedelta
import logging
from newspaper import Article
import dateutil.parser
import json
import time
import sys
from pathlib import Path
import pytz

# Add parent directory to path to allow imports
sys.path.append(str(Path(__file__).parent.parent))
from utils import fetch_url  # utils.py is in the root directory

class BaseScraper:
    def __init__(self, source_name, base_url, article_url_pattern):
        self.source_name = source_name
        self.base_url = base_url
        self.article_url_pattern = article_url_pattern
        self.max_links_to_crawl = 5000
        # Set timezone to UTC for consistent date handling
        self.timezone = pytz.UTC
        # Get current date in UTC
        self.current_date = datetime.now(self.timezone)
        # Set cutoff date to 24 hours ago
        self.cutoff_date = self.current_date - timedelta(days=1)

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

    def is_recent_article(self, published_at):
        """Check if article was published within last 24 hours"""
        if not published_at:
            return False
        # Convert naive datetime to UTC if it doesn't have timezone
        if published_at.tzinfo is None:
            published_at = self.timezone.localize(published_at)
        # Convert to UTC if it has different timezone
        published_at = published_at.astimezone(self.timezone)
        return published_at >= self.cutoff_date

    def parse_date(self, date_str, date_elem):
        """Parse date from various formats and elements"""
        if not date_str and not date_elem:
            return None
        
        # Try to get date from datetime attribute first
        if date_elem and date_elem.get('datetime'):
            try:
                return dateutil.parser.parse(date_elem['datetime'])
            except:
                pass

        # Try to get date from content
        if date_str:
            # Common date formats
            date_formats = [
                '%Y-%m-%dT%H:%M:%S%z',  # ISO 8601 with timezone
                '%Y-%m-%dT%H:%M:%S.%f%z',  # ISO 8601 with microseconds
                '%Y-%m-%d %H:%M:%S%z',  # Space separated with timezone
                '%Y-%m-%d %H:%M:%S',  # Space separated without timezone
                '%B %d, %Y',  # Month name, day, year
                '%d %B %Y',  # Day, month name, year
                '%Y-%m-%d',  # Year-month-day
                '%m/%d/%Y',  # Month/day/year
                '%d/%m/%Y',  # Day/month/year
            ]
            
            # Try parsing with each format
            for fmt in date_formats:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    # If no timezone info, assume UTC
                    if dt.tzinfo is None:
                        dt = self.timezone.localize(dt)
                    return dt
                except:
                    continue
            
            # Try dateutil as fallback
            try:
                return dateutil.parser.parse(date_str)
            except:
                pass
        
        return None

    def extract_date(self, soup):
        """Extract and validate date from article"""
        # Common date element patterns
        date_patterns = [
            'time',  # HTML5 time element
            'span.date', 'span.timestamp', 'span.published',  # Common span classes
            'div.date', 'div.timestamp', 'div.published',  # Common div classes
            'meta[property="article:published_time"]',  # Open Graph meta
            'meta[name="pubdate"]',  # Meta pubdate
            'meta[name="publishdate"]',  # Meta publishdate
            'meta[name="date"]',  # Meta date
        ]
        
        # Try each pattern
        for pattern in date_patterns:
            try:
                if pattern.startswith('meta'):
                    date_elem = soup.select_one(pattern)
                    if date_elem and date_elem.get('content'):
                        return self.parse_date(date_elem['content'], date_elem)
                else:
                    date_elem = soup.find(pattern.split('.')[0], class_=pattern.split('.')[1] if '.' in pattern else None)
                    if date_elem:
                        return self.parse_date(date_elem.get_text(strip=True), date_elem)
            except:
                continue
        
        return None

    def validate_article(self, article):
        """Validate article content and date"""
        if not article:
            return False
            
        # Check required fields
        if not article.get('title') or not article.get('content'):
            return False
            
        # Check content length
        if len(article['content'].strip()) < 100:  # Minimum 100 characters
            return False
            
        # Check date
        if not self.is_recent_article(article.get('published_at')):
            return False
            
        return True

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

