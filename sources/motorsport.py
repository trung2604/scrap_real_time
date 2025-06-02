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

class MotorsportScraper(BaseScraper):
    def __init__(self):
        # Motorsport.com có dạng link bài báo:
        # - https://www.motorsport.com/f1/news/title-article/
        # - https://www.motorsport.com/nascar/news/title-article/
        # - https://www.motorsport.com/indycar/news/title-article/
        article_url_pattern = r"https://www\.motorsport\.com/(?:f1|nascar|indycar|motogp|wec|formula-e|dtm|wrc|gt|endurance|rally|rallycross|drift|drag|karting|v8supercars|supercars|supergt|superformula|superbike|motocross|enduro|rally-raid|touring|tcr|wtcr|wtcc|btcc|dtm|supercars|supergt|superformula|superbike|motocross|enduro|rally-raid|touring|tcr|wtcr|wtcc|btcc)/news/[a-z0-9-]+(?:/[a-z0-9-]+)*/?"
        self.news_sections = [
            '/news/', '/f1/news/', '/motogp/news/'
        ]
        super().__init__("Motorsport.com", "https://www.motorsport.com", article_url_pattern)
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
        # Setup Chrome options for Selenium with additional settings
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--disable-infobars')
        self.chrome_options.add_argument('--disable-notifications')
        self.chrome_options.add_argument('--disable-popup-blocking')
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_argument('--disable-images')  # Disable images to speed up loading
        self.chrome_options.add_argument('--disable-javascript')  # Disable JavaScript for article pages
        self.chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # Disable images in Blink
        self.chrome_options.add_argument('--disk-cache-size=1')  # Minimize disk cache
        self.chrome_options.add_argument('--media-cache-size=1')  # Minimize media cache
        self.chrome_options.add_argument('--disable-application-cache')  # Disable application cache
        self.chrome_options.add_argument('--disable-cache')  # Disable browser cache
        self.chrome_options.add_argument('--disable-offline-load-stale-cache')  # Disable offline cache
        self.chrome_options.add_argument('--disable-background-networking')  # Disable background networking
        self.chrome_options.add_argument('--disable-default-apps')  # Disable default apps
        self.chrome_options.add_argument('--disable-sync')  # Disable sync
        self.chrome_options.add_argument('--disable-translate')  # Disable translate
        self.chrome_options.add_argument('--metrics-recording-only')  # Disable metrics recording
        self.chrome_options.add_argument('--no-first-run')  # Disable first run
        self.chrome_options.add_argument('--safebrowsing-disable-auto-update')  # Disable safebrowsing
        self.chrome_options.add_argument('--password-store=basic')  # Disable password store
        self.chrome_options.add_argument('--use-mock-keychain')  # Use mock keychain
        self.chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        self.driver = None
        self.wait = None
        self._init_driver()
        # Configure logging
        self.logger = logging.getLogger('Motorsport')
        self.logger.setLevel(logging.INFO)
        # Create console handler with formatting
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def _init_driver(self):
        """Initialize Selenium WebDriver with retry logic"""
        max_retries = 3
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                self.driver = webdriver.Chrome(options=self.chrome_options)
                self.driver.set_page_load_timeout(20)
                self.driver.set_script_timeout(20)
                self.wait = WebDriverWait(self.driver, 15)
                # Test the driver with a simple page
                self.driver.get("https://www.motorsport.com")
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                self.logger.info("Successfully initialized WebDriver")
                return
            except Exception as e:
                self.logger.error(f"Failed to initialize WebDriver (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise Exception("Failed to initialize WebDriver after multiple attempts")

    def _get_soup(self, url):
        """Get BeautifulSoup object using Selenium for JavaScript content with SSL verification and retry logic"""
        max_retries = 3
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                if not self.driver:
                    self._init_driver()
                # Always enable JavaScript for Motorsport.com
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
                self.logger.error(f"Failed to fetch {url} (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    try:
                        self._init_driver()
                    except:
                        pass
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    return None

    def _extract_links_with_pagination(self, section_url):
        links = []
        page = 1
        while len(links) < self.max_links_to_crawl:
            url = section_url if page == 1 else f"{section_url}?page={page}"
            self.logger.info(f"Fetching page {page}")
            soup = self._get_soup(url)
            if not soup:
                self.logger.warning(f"Could not fetch page {page}")
                break
            new_links = []
            article_containers = soup.find_all(['div', 'article'], class_=re.compile('article-list-item|article-card|news-card|story-card|content-list-item|article-list|content-list'))
            for container in article_containers:
                a = container.find('a', href=True)
                if not a:
                    parent = container.find_parent('a', href=True)
                    if parent:
                        a = parent
                if a:
                    href = a['href']
                    if href.startswith('/'):
                        href = urljoin(self.base_url, href)
                    if re.match(self.article_url_pattern, href):
                        if href not in links and href not in new_links:
                            new_links.append(href)
            if not new_links:
                self.logger.info(f"No new links found on page {page}, stopping pagination")
                break
            links.extend(new_links)
            self.logger.info(f"Found {len(new_links)} new links on page {page}, total: {len(links)}")
            if len(links) >= self.max_links_to_crawl:
                self.logger.info(f"Reached max links limit ({self.max_links_to_crawl})")
                break
            page += 1
            time.sleep(3)
        return links[:self.max_links_to_crawl]

    def scrape_article_content(self, url):
        """Override scrape_article_content to handle JavaScript content"""
        try:
            soup = self._get_soup(url)
            if not soup:
                return None

            # Extract title
            title_elem = soup.find('h1', class_=re.compile('article-title|headline|title'))
            if not title_elem:
                title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract content
            content_elem = soup.find('div', class_=re.compile('article-body|article-content|story-body'))
            if not content_elem:
                content_elem = soup.find('article')
            if content_elem:
                for unwanted in content_elem.find_all(['script', 'style', 'iframe', 'div.article-share', 'div.article-tags', 'div.article-related', 'div.social-share']):
                    unwanted.decompose()
                content = ' '.join([p.get_text(strip=True) for p in content_elem.find_all(['p', 'h2', 'h3', 'h4'])])
            else:
                content = None

            # Extract date
            date_elem = soup.find('time') or soup.find('span', class_=re.compile('date|timestamp|published'))
            published_at = None
            if date_elem and date_elem.get('datetime'):
                try:
                    published_at = dateutil.parser.parse(date_elem['datetime'])
                except:
                    pass

            if title and content:
                self.logger.info(f"Successfully scraped article: {title[:50]}...")
                return {
                    'title': title,
                    'content': content,
                    'published_at': published_at,
                    'url': url,
                    'source': self.source_name
                }
            self.logger.warning(f"Failed to extract content from article: {url}")
            return None
        except Exception as e:
            self.logger.error(f"Error scraping article {url}: {str(e)}")
            return None

    def scrape_all_articles(self):
        articles = []
        try:
            for section in self.news_sections:
                section_url = urljoin(self.base_url, section)
                self.logger.info(f"Starting to scrape section: {section}")
                links = self._extract_links_with_pagination(section_url)
                if len(links) == 0:
                    self.logger.warning(f"No article links found in section {section}")
                    continue
                self.logger.info(f"Found {len(links)} articles in section {section}")
                for link in links:
                    if any(article['url'] == link for article in articles):
                        continue
                    try:
                        article = self.scrape_article_content(link)
                        if article:
                            articles.append({
                                'title': article.get('title', ''),
                                'content': article.get('content', ''),
                                'url': link,
                                'published_at': article.get('published_at').isoformat() + 'Z' if article.get('published_at') else None,
                                'source': self.source_name
                            })
                        time.sleep(2)
                    except Exception as e:
                        self.logger.error(f"Error scraping article {link}: {str(e)}")
                        continue
        except Exception as e:
            self.logger.error(f"Error in scrape_all_articles: {str(e)}")
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
        self.logger.info(f"Finished scraping. Total articles scraped: {len(articles)}")
        return articles

scraper = MotorsportScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper.scrape_article_content 