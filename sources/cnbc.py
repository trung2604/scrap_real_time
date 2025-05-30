from .base_scraper import BaseScraper
from datetime import datetime, timedelta
from newspaper import Article
import logging
import dateutil.parser
import json
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import time
import certifi
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class CNBCScraper(BaseScraper):
    def __init__(self):
        # Update article pattern to be less restrictive
        article_url_pattern = r"https://www\.cnbc\.com/(?:\d{4}/\d{2}/\d{2}/|select/|2024/|2023/|2025/|markets/|business/|technology/|politics/|economy/|investing/|personal-finance/|health-and-science/|wealth/|sports/|life/|small-business/|fintech/|financial-advisors/|options-action/|etf-street/|earnings/|trader-talk/|cybersecurity/|ai-artificial-intelligence/|enterprise/|internet/|media/|mobile/|social-media/|cnbc-disruptors/|tech-guide/|white-house/|policy/|defense/|congress/|equity-opportunity/|europe-politics/|china-politics/|asia-politics/|world-politics/).+"
        self.news_sections = [
            '/sports/',
            '/sports/football/',
            '/sports/basketball/',
            '/sports/tennis/',
            '/sports/golf/',
            '/sports/baseball/',
            '/sports/hockey/',
            # Thêm các chuyên mục con thể thao khác nếu có
        ]
        # Reduce exclude keywords to only filter out non-article content
        self.exclude_keywords = ["video", "slideshow", "watch", "live", "tv", "subscribe"]
        super().__init__(
            source_name="CNBC",
            base_url="https://www.cnbc.com",
            article_url_pattern=article_url_pattern
        )
        self.max_links_to_crawl = 3000
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        # Setup session with retry and SSL verification
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.verify = certifi.where()

    def _get_soup(self, url):
        """Get BeautifulSoup object with SSL verification and retry strategy"""
        try:
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logging.error(f"[CNBC] Error fetching {url}: {e}")
            return None

    def _extract_links(self, soup, base_url):
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('/'):
                href = urljoin(self.base_url, href)
            elif not href.startswith('http'):
                href = urljoin(base_url, href)
            
            # Check if URL matches pattern and doesn't contain excluded keywords
            if re.match(self.article_url_pattern, href):
                if any(x in href.lower() for x in self.exclude_keywords):
                    logging.debug(f"[CNBC] Excluding URL due to keywords: {href}")
                    continue
                if href not in links:  # Avoid duplicates
                    links.append(href)
                    if len(links) >= self.max_links_to_crawl:
                        break
        
        logging.info(f"[CNBC] Found {len(links)} valid links from {base_url}")
        return links

    def _extract_links_with_pagination(self, section_url):
        links = []
        page = 1
        while len(links) < self.max_links_to_crawl:
            # CNBC dùng dạng phân trang ?page={page}
            url = section_url + f'?page={page}' if page > 1 else section_url
            logging.info(f"[CNBC] Fetching page {page} from {url}")
            soup = self._get_soup(url)
            if not soup:
                logging.warning(f"[CNBC] Could not fetch page {page} from {url}")
                break
            new_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/'):
                    href = urljoin(self.base_url, href)
                elif not href.startswith('http'):
                    href = urljoin(section_url, href)
                if re.match(self.article_url_pattern, href):
                    if any(x in href.lower() for x in self.exclude_keywords):
                        continue
                    if href not in links and href not in new_links:
                        new_links.append(href)
                        logging.debug(f"[CNBC] Found article link: {href}")
            if not new_links:
                logging.info(f"[CNBC] No new links found on page {page}, stopping pagination")
                break
            links.extend(new_links)
            if page == 1:
                logging.info(f"[CNBC] First 5 links from {section_url}: {links[:5]}")
            logging.info(f"[CNBC] Total links found in {section_url} after page {page}: {len(links)}")
            if len(links) >= self.max_links_to_crawl:
                logging.info(f"[CNBC] Reached max links limit ({self.max_links_to_crawl})")
                break
            page += 1
            time.sleep(2)  # Add delay between pages
        return links[:self.max_links_to_crawl]

    def scrape_all_articles(self):
        articles = []
        logging.info(f"[CNBC] Starting to scrape all articles (no date filter)")
        try:
            for section in self.news_sections:
                section_url = urljoin(self.base_url, section)
                logging.info(f"[CNBC] Scraping section: {section_url}")
                links = self._extract_links_with_pagination(section_url)
                logging.info(f"[CNBC] Found {len(links)} links in section {section}")
                if len(links) == 0:
                    logging.warning(f"[CNBC] No article links found in section {section_url}")
                for link in links:
                    if any(article['url'] == link for article in articles):
                        logging.debug(f"[CNBC] Skipping duplicate article: {link}")
                        continue
                    try:
                        logging.info(f"[CNBC] Scraping article: {link}")
                        article = self.scrape_article_content(link)
                        if article:
                            articles.append({
                                'title': article.get('title', ''),
                                'content': article.get('content', ''),
                                'url': link,
                                'published_at': article.get('published_at').isoformat() + 'Z' if article.get('published_at') else None,
                                'source': self.source_name
                            })
                            logging.info(f"[CNBC] Successfully scraped article: {article.get('title', '')}")
                        else:
                            logging.warning(f"[CNBC] Failed to scrape article: {link}")
                        time.sleep(2)  # Add delay between articles
                    except Exception as e:
                        logging.error(f"[CNBC] Error scraping article {link}: {e}")
                        continue
        except Exception as e:
            logging.error(f"[CNBC] Error in scrape_all_articles: {e}")
        logging.info(f"[CNBC] Found {len(articles)} articles in total")
        return articles

    def scrape_article_content(self, url):
        try:
            soup = self._get_soup(url)
            if not soup:
                logging.error(f"[CNBC] Failed to get soup for article: {url}")
                return None

            # Try multiple methods to get the article content
            article = {}
            
            # 1. Try newspaper3k first
            try:
                newspaper_article = self._extract_with_newspaper(url)
                if newspaper_article and newspaper_article.get('text'):
                    article = {
                        'title': newspaper_article.get('title', ''),
                        'content': newspaper_article.get('text', ''),
                        'published_at': newspaper_article.get('publish_date'),
                        'source': self.source_name,  # Add source field
                        'url': url,  # Add URL field
                        'scraped_at': datetime.utcnow()  # Add scraped_at field
                    }
                    if article['published_at']:
                        logging.info(f"[CNBC] Successfully extracted article using newspaper3k: {url}")
                        return article
            except Exception as e:
                logging.warning(f"[CNBC] Newspaper3k extraction failed for {url}: {e}")

            # 2. Try direct extraction if newspaper3k failed
            try:
                # Get title
                title = self._extract_title(soup)
                if not title:
                    logging.warning(f"[CNBC] Could not extract title from {url}")
                    return None
                article['title'] = title

                # Get content
                content = self._extract_content(soup)
                if not content:
                    logging.warning(f"[CNBC] Could not extract content from {url}")
                    return None
                article['content'] = content

                # Get date
                published_at = self._extract_date(soup)
                if not published_at:
                    # Try to get date from URL as last resort
                    url_date = self._extract_date_from_url(url)
                    if url_date:
                        published_at = url_date
                        logging.info(f"[CNBC] Using date from URL: {published_at}")
                    else:
                        logging.warning(f"[CNBC] Could not extract date from {url}")
                        return None
                article['published_at'] = published_at

                article['source'] = self.source_name  # Add source field
                article['url'] = url  # Add URL field
                article['scraped_at'] = datetime.utcnow()  # Add scraped_at field

                logging.info(f"[CNBC] Successfully extracted article using direct extraction: {url}")
                return article

            except Exception as e:
                logging.error(f"[CNBC] Direct extraction failed for {url}: {e}")
                return None

        except Exception as e:
            logging.error(f"[CNBC] Error scraping article {url}: {e}")
            return None

    def _extract_title(self, soup):
        try:
            # Try multiple title selectors
            title_selectors = [
                'h1.article-title',  # Main article title
                'h1[data-testid="article-title"]',  # Data attribute based
                'h1.article__title',  # Alternative title class
                'h1'  # Fallback to any h1
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title:
                        return title
            
            logging.warning("[CNBC] Could not find title with any selector")
            return None
            
        except Exception as e:
            logging.error(f"[CNBC] Error extracting title: {e}")
            return None

    def _extract_content(self, soup):
        try:
            # Try multiple content selectors
            content_selectors = [
                'div.article__body',  # Main article body
                'div.group',  # Alternative article body
                'div[data-module="ArticleBody"]',  # Data attribute based
                'div.article-content',  # Another common container
                'article'  # Fallback to article tag
            ]
            
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    # Remove unwanted elements
                    for unwanted in content_div.select('div.related-content, div.article-tags, div.article-share, script, style, .article-video, .article-image, .article-related'):
                        unwanted.decompose()
                    
                    # Get text content
                    content = ' '.join([p.get_text(strip=True) for p in content_div.find_all(['p', 'h2', 'h3', 'h4'])])
                    if content and len(content) > 100:  # Basic validation
                        return content
            
            logging.warning("[CNBC] Could not find content with any selector")
            return None
            
        except Exception as e:
            logging.error(f"[CNBC] Error extracting content: {e}")
            return None

    def _extract_date(self, soup):
        """Extract date from article content using multiple methods"""
        try:
            # Try meta tags first
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date and meta_date.get('content'):
                date = dateutil.parser.parse(meta_date['content'])
                return date.replace(tzinfo=None)  # Make timezone-naive
            
            # Try article time element
            time_elem = soup.find('time', {'class': 'article-timestamp'})
            if time_elem and time_elem.get('datetime'):
                date = dateutil.parser.parse(time_elem['datetime'])
                return date.replace(tzinfo=None)  # Make timezone-naive
            
            # Try date in article header
            date_elem = soup.find('span', {'class': 'article-timestamp'})
            if date_elem:
                try:
                    date = dateutil.parser.parse(date_elem.text.strip())
                    return date.replace(tzinfo=None)  # Make timezone-naive
                except:
                    pass
            
            # Try date in article metadata
            meta_elem = soup.find('div', {'class': 'article-meta'})
            if meta_elem:
                date_text = meta_elem.find('time')
                if date_text and date_text.get('datetime'):
                    date = dateutil.parser.parse(date_text['datetime'])
                    return date.replace(tzinfo=None)  # Make timezone-naive
            
            # Try date in URL as fallback
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', soup.url)
            if date_match:
                year, month, day = date_match.groups()
                try:
                    return datetime(int(year), int(month), int(day))  # Already timezone-naive
                except:
                    pass
            
            logging.warning(f"[CNBC] Could not extract date for article: {soup.url}")
            return None
            
        except Exception as e:
            logging.error(f"[CNBC] Error extracting date: {e}")
            return None

    def _extract_date_from_url(self, url):
        """Extract date from URL if possible"""
        try:
            # Try to find date in URL format like /2024/01/20/title
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            if date_match:
                year, month, day = date_match.groups()
                return dateutil.parser.parse(f"{year}-{month}-{day}")
            return None
        except Exception as e:
            logging.error(f"[CNBC] Error extracting date from URL: {e}")
            return None

scraper = CNBCScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper.scrape_article_content

