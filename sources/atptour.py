from sources.base_scraper import BaseScraper
from urllib.parse import urljoin
import re
import logging
import requests
from bs4 import BeautifulSoup
import time
import certifi
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import dateutil.parser

class ATPTourScraper(BaseScraper):
    def __init__(self):
        # ATP Tour có dạng link bài báo:
        # - https://www.atptour.com/en/news/title-article
        # - https://www.atptour.com/en/tournaments/title-article
        # - https://www.atptour.com/en/players/title-article
        article_url_pattern = r"https://www\.atptour\.com/en/(?:news|tournaments|players)/[a-z0-9-]+(?:/[a-z0-9-]+)*/?"
        self.news_sections = [
            '/en/news/', '/en/media/', '/en/video/'
        ]
        super().__init__("ATP Tour", "https://www.atptour.com", article_url_pattern)
        self.max_links_to_crawl = 5000
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
        # Setup Chrome options for Selenium
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.chrome_options = chrome_options

    def _get_soup(self, url):
        """Get BeautifulSoup object using Selenium for JavaScript content with SSL verification and retry logic"""
        max_retries = 3
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                if not self.driver:
                    self._init_driver()
                # Always enable JavaScript for ATP Tour
                self.chrome_options.remove_argument('--disable-javascript')
                self.driver.get(url)
                # Wait for article content to load with multiple possible selectors
                selectors = [
                    (By.CLASS_NAME, "article-list"),
                    (By.CLASS_NAME, "article-list-item"),
                    (By.CLASS_NAME, "article-card"),
                    (By.CLASS_NAME, "news-card"),
                    (By.CLASS_NAME, "story-card"),
                    (By.CLASS_NAME, "content-list"),
                    (By.CLASS_NAME, "content-list-item"),
                    (By.TAG_NAME, "article"),
                    (By.CLASS_NAME, "article-body"),
                    (By.CLASS_NAME, "article-content"),
                    (By.CLASS_NAME, "story-body"),
                    (By.TAG_NAME, "body")  # Fallback to body tag
                ]
                for selector in selectors:
                    try:
                        self.wait.until(EC.presence_of_element_located(selector))
                        break
                    except:
                        continue
                # Additional wait for dynamic content and JavaScript execution
                time.sleep(5)  # Increased wait time for JavaScript content
                if not '/news/' in url or url.endswith('/news/'):
                    # Execute JavaScript to scroll and trigger lazy loading only for list pages
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    self.driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(2)
                return BeautifulSoup(self.driver.page_source, 'html.parser')
            except Exception as e:
                logging.error(f"[ATP Tour] Error fetching {url} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    try:
                        self._init_driver()  # Try to reinitialize driver
                    except:
                        pass
                    time.sleep(retry_delay)
                else:
                    return None

    def _extract_links_with_pagination(self, section_url):
        links = []
        page = 1
        while len(links) < self.max_links_to_crawl:
            # ATP Tour dùng ?page=2, ?page=3, etc cho phân trang
            url = section_url if page == 1 else f"{section_url}?page={page}"
            logging.info(f"[ATP Tour] Fetching page {page} from {url}")
            soup = self._get_soup(url)
            if not soup:
                logging.warning(f"[ATP Tour] Could not fetch page {page} from {url}")
                break
            new_links = []
            # Look for article links in specific containers
            article_containers = soup.find_all('div', class_=re.compile('article-card|news-card'))
            for container in article_containers:
                a = container.find('a', href=True)
                if a:
                    href = a['href']
                    if href.startswith('/'):
                        href = urljoin(self.base_url, href)
                    if re.match(self.article_url_pattern, href):
                        if href not in links and href not in new_links:
                            new_links.append(href)
                            logging.debug(f"[ATP Tour] Found article link: {href}")
            if not new_links:
                logging.info(f"[ATP Tour] No new links found on page {page}, stopping pagination")
                break
            links.extend(new_links)
            if page == 1:
                logging.info(f"[ATP Tour] First 5 links from {section_url}: {links[:5]}")
            logging.info(f"[ATP Tour] Total links found in {section_url} after page {page}: {len(links)}")
            if len(links) >= self.max_links_to_crawl:
                logging.info(f"[ATP Tour] Reached max links limit ({self.max_links_to_crawl})")
                break
            page += 1
            time.sleep(2)  # Add delay between pages
        return links[:self.max_links_to_crawl]

    def scrape_article_content(self, url):
        """Override scrape_article_content to handle JavaScript content"""
        try:
            soup = self._get_soup(url)
            if not soup:
                return None

            # Extract title
            title_elem = soup.find('h1', class_=re.compile('article-title|headline'))
            if not title_elem:
                title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract content
            content_elem = soup.find('div', class_=re.compile('article-body|article-content'))
            if not content_elem:
                content_elem = soup.find('article')
            if content_elem:
                # Remove unwanted elements
                for unwanted in content_elem.find_all(['script', 'style', 'iframe', 'div.article-share']):
                    unwanted.decompose()
                content = ' '.join([p.get_text(strip=True) for p in content_elem.find_all(['p', 'h2', 'h3', 'h4'])])
            else:
                content = None

            # Extract date
            date_elem = soup.find('time') or soup.find('span', class_=re.compile('date|timestamp'))
            published_at = None
            if date_elem and date_elem.get('datetime'):
                try:
                    published_at = dateutil.parser.parse(date_elem['datetime'])
                except:
                    pass

            if title and content:
                return {
                    'title': title,
                    'content': content,
                    'published_at': published_at,
                    'url': url,
                    'source': self.source_name
                }
            return None
        except Exception as e:
            logging.error(f"[ATP Tour] Error scraping article {url}: {e}")
            return None

    def scrape_all_articles(self):
        articles = []
        try:
            for section in self.news_sections:
                section_url = urljoin(self.base_url, section)
                logging.info(f"[ATP Tour] Starting to scrape section: {section_url}")
                links = self._extract_links_with_pagination(section_url)
                logging.info(f"[ATP Tour] Found {len(links)} links in section {section}")
                if len(links) == 0:
                    logging.warning(f"[ATP Tour] No article links found in section {section_url}")
                for link in links:
                    article = self.scrape_article_content(link)
                    if article:
                        articles.append({
                            'title': article.get('title', ''),
                            'content': article.get('content', ''),
                            'url': link,
                            'published_at': article.get('published_at').isoformat() + 'Z' if article.get('published_at') else None,
                            'source': self.source_name
                        })
                        logging.info(f"[ATP Tour] Successfully scraped article: {article.get('title', '')}")
                    else:
                        logging.warning(f"[ATP Tour] Failed to scrape article: {link}")
                    time.sleep(2)  # Add delay between articles
        finally:
            self.driver.quit()  # Make sure to close the browser
        return articles

scraper = ATPTourScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper.scrape_article_content 