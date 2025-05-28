from .base_scraper import BaseScraper
from datetime import datetime, timedelta
import logging
from urllib.parse import urljoin
import re
import dateutil.parser
import json
from newspaper import Article

class SkySportsScraper(BaseScraper):
    def __init__(self):
        article_url_pattern = r"https://www\.skysports\.com/(?:football|f1|cricket|tennis|boxing|golf|rugby-union|rugby-league|nfl|racing|darts|netball|mma|news)/news/\d+/.+"
        self.news_sections = [
            '/news/latest/', '/news/today/', '/news/breaking/', '/news/headlines/',
            '/football/news/', '/f1/news/', '/cricket/news/', '/tennis/news/',
            '/boxing/news/', '/golf/news/', '/rugby-union/news/', '/rugby-league/news/',
            '/nfl/news/', '/racing/news/', '/darts/news/', '/netnetball/news/', '/mma/news/',
            '/news/'
        ]
        self.exclude_keywords = ["video", "podcast", "live-blog", "watch", "tv", "live", "highlights"]
        super().__init__(
            source_name="Sky Sports",
            base_url="https://www.skysports.com",
            article_url_pattern=article_url_pattern
        )
        self.max_links_to_crawl = 1000

    def scrape_all_articles(self):
        articles = []
        now = datetime.utcnow()
        cutoff_time = now - timedelta(hours=48)  # Scrape articles from last 48 hours
        logging.info(f"[SkySports] Starting to scrape articles from {cutoff_time} to {now}")

        try:
            # Scrape homepage
            homepage_url = self.base_url
            logging.info(f"[SkySports] Scraping homepage: {homepage_url}")
            soup = self._get_soup(homepage_url)
            if soup:
                links = self._extract_links(soup, homepage_url)
                logging.info(f"[SkySports] Found {len(links)} links on homepage")

                for link in links:
                    try:
                        article_soup = self._get_soup(link)
                        if not article_soup:
                            continue

                        date = self._extract_date(article_soup, link)
                        if not date:
                            logging.warning(f"[SkySports] Could not extract date for {link}")
                            continue

                        # Loại bỏ múi giờ để làm cho date thành offset-naive
                        date = date.replace(tzinfo=None)
                        logging.info(f"[SkySports] Article date: {date} for {link}")

                        if date < cutoff_time:
                            logging.info(f"[SkySports] Article too old: {date} for {link}")
                            continue

                        title = self._extract_title(article_soup)
                        content = self._extract_content(article_soup)

                        if title and content:
                            articles.append({
                                'title': title,
                                'content': content,
                                'url': link,
                                'published_at': date,
                                'source': self.source_name
                            })
                            logging.info(f"[SkySports] Successfully scraped article: {title}")

                    except Exception as e:
                        logging.error(f"[SkySports] Error scraping article {link}: {e}")
                        continue

            # Scrape news sections
            for section in self.news_sections:
                section_url = urljoin(self.base_url, section)
                logging.info(f"[SkySports] Scraping section: {section_url}")

                try:
                    soup = self._get_soup(section_url)
                    if not soup:
                        continue

                    links = self._extract_links(soup, section_url)
                    logging.info(f"[SkySports] Found {len(links)} links in section {section}")

                    for link in links:
                        if any(article['url'] == link for article in articles):
                            continue

                        try:
                            article_soup = self._get_soup(link)
                            if not article_soup:
                                continue

                            date = self._extract_date(article_soup, link)
                            if not date:
                                logging.warning(f"[SkySports] Could not extract date for {link}")
                                continue

                            # Loại bỏ múi giờ để làm cho date thành offset-naive
                            date = date.replace(tzinfo=None)
                            logging.info(f"[SkySports] Article date: {date} for {link}")

                            if date < cutoff_time:
                                logging.info(f"[SkySports] Article too old: {date} for {link}")
                                continue

                            title = self._extract_title(article_soup)
                            content = self._extract_content(article_soup)

                            if title and content:
                                articles.append({
                                    'title': title,
                                    'content': content,
                                    'url': link,
                                    'published_at': date,
                                    'source': self.source_name
                                })
                                logging.info(f"[SkySports] Successfully scraped article: {title}")

                        except Exception as e:
                            logging.error(f"[SkySports] Error scraping article {link}: {e}")
                            continue

                except Exception as e:
                    logging.error(f"[SkySports] Error scraping section {section_url}: {e}")
                    continue

        except Exception as e:
            logging.error(f"[SkySports] Error in scrape_all_articles: {e}")

        logging.info(f"[SkySports] Found {len(articles)} articles in total")
        return articles

    def _extract_links(self, soup, base_url):
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('/'):
                href = urljoin(self.base_url, href)
            elif not href.startswith('http'):
                href = urljoin(base_url, href)

            if re.match(self.article_url_pattern, href):
                if any(x in href.lower() for x in self.exclude_keywords):
                    logging.debug(f"[SkySports] Excluding URL due to keywords: {href}")
                    continue
                if href not in links:
                    links.append(href)
                    if len(links) >= self.max_links_to_crawl:
                        break

        logging.info(f"[SkySports] Found {len(links)} valid links from {base_url}")
        return links

    def _extract_date(self, soup, url):
        """Extract date from article content using multiple methods"""
        try:
            # Try meta tags
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date and meta_date.get('content'):
                try:
                    return dateutil.parser.parse(meta_date['content'])
                except Exception as e:
                    logging.debug(f"[SkySports] Meta date parsing failed: {e}")

            # Try JSON-LD
            scripts = soup.find_all('script', {'type': 'application/ld+json'})
            for script in scripts:
                try:
                    if script.string:
                        data = json.loads(script.string)
                        if isinstance(data, dict):
                            for field in ['datePublished', 'dateCreated']:
                                if field in data:
                                    return dateutil.parser.parse(data[field])
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and field in item:
                                    return dateutil.parser.parse(item[field])
                except Exception as e:
                    logging.debug(f"[SkySports] JSON-LD parsing failed: {e}")

            # Try article time element
            time_elem = soup.find('time')
            if time_elem and time_elem.get('datetime'):
                try:
                    return dateutil.parser.parse(time_elem['datetime'])
                except Exception as e:
                    logging.debug(f"[SkySports] Time element parsing failed: {e}")

            # Try date in article header
            date_elem = soup.find('span', {'class': re.compile('timestamp|date|published')})
            if date_elem:
                try:
                    return dateutil.parser.parse(date_elem.text.strip())
                except Exception as e:
                    logging.debug(f"[SkySports] Header date parsing failed: {e}")

            # Try date in article metadata
            meta_elem = soup.find('div', {'class': re.compile('meta|article-info|date')})
            if meta_elem:
                date_text = meta_elem.find('time') or meta_elem.find('span')
                if date_text and date_text.get('datetime'):
                    try:
                        return dateutil.parser.parse(date_text['datetime'])
                    except Exception as e:
                        logging.debug(f"[SkySports] Metadata date parsing failed: {e}")

            # Try date in URL as fallback
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            if date_match:
                year, month, day = date_match.groups()
                try:
                    return datetime(int(year), int(month), int(day))
                except Exception as e:
                    logging.debug(f"[SkySports] URL date parsing failed: {e}")

            logging.warning(f"[SkySports] Could not extract date for article: {url}")
            return None

        except Exception as e:
            logging.error(f"[SkySports] Could not extract date for {url}: {str(e)}")
            return None

    def _extract_title(self, soup):
        """Extract article title using multiple methods"""
        try:
            # Try multiple title selectors
            title_selectors = [
                'h1.article__headline',  # Main article title
                'h1.article__title',     # Alternative title class
                'h1.headline',           # Another common class
                'h1'                     # Fallback to any h1
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title:
                        return title
            
            # Try meta title as fallback
            meta_title = soup.find('meta', property='og:title')
            if meta_title and meta_title.get('content'):
                return meta_title['content'].strip()
            
            logging.warning("[SkySports] Could not find title with any selector")
            return None
            
        except Exception as e:
            logging.error(f"[SkySports] Error extracting title: {e}")
            return None

    def _extract_content(self, soup):
        """Extract article content using multiple methods"""
        try:
            # Try multiple content selectors (updated for new Sky Sports layout)
            content_selectors = [
                'div.sdc-article-body',         # New main article body
                'section.sdc-article-body',     # Sometimes used as section
                'div.sdc-article-main',         # Alternative main container
                'div.article__body',            # Old main article body
                'div.article-content',          # Old alternative
                'div.article__content',         # Old another
                'article'                       # Fallback
            ]
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    # Remove unwanted elements
                    for unwanted in content_div.select('div.article-tags, div.article-share, script, style, .article-video, .article-image, .article-related, aside, figure, .sdc-article-widget'):
                        unwanted.decompose()
                    # Get text content
                    content = ' '.join([p.get_text(strip=True) for p in content_div.find_all(['p', 'h2', 'h3', 'h4'])])
                    if content and len(content) > 100:  # Basic validation
                        return content
            # Try newspaper3k as fallback
            try:
                article = Article(soup.url)
                article.download()
                article.parse()
                if article.text and len(article.text) > 100:
                    return article.text
            except Exception as e:
                logging.debug(f"[SkySports] Newspaper3k fallback failed: {e}")
            logging.warning("[SkySports] Could not find content with any selector")
            return None
        except Exception as e:
            logging.error(f"[SkySports] Error extracting content: {e}")
            return None

scraper = SkySportsScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper