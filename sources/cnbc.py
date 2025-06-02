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
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

class CNBCScraper(BaseScraper):
    def __init__(self):
        # Configure logging first
        self.logger = logging.getLogger('CNBC')
        self.logger.setLevel(logging.INFO)
        # Create console handler with formatting
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # Update article pattern to be more flexible
        article_url_pattern = r"https://www\.cnbc\.com/(?:sports|markets|business|technology|politics|economy|investing|personal-finance|health-and-science|wealth|life|small-business|fintech|financial-advisors|options-action|etf-street|earnings|trader-talk|cybersecurity|ai-artificial-intelligence|enterprise|internet|media|mobile|social-media|cnbc-disruptors|tech-guide|white-house|policy|defense|congress|equity-opportunity|europe-politics|china-politics|asia-politics|world-politics)/[a-z0-9-]+(?:/[a-z0-9-]+)*/?"
        self.news_sections = [
            '/sports/',
            '/sports/football/',
            '/sports/basketball/',
            '/sports/tennis/',
            '/sports/golf/',
            '/sports/baseball/',
            '/sports/hockey/',
            '/sports/soccer/',
            '/sports/racing/',
            '/sports/boxing/',
            '/sports/mma/',
            '/sports/wrestling/',
            '/sports/olympics/',
            '/sports/other-sports/'
        ]
        # Reduce exclude keywords to only filter out non-article content
        self.exclude_keywords = ["video", "slideshow", "watch", "live", "tv", "subscribe", "gallery", "pictures", "photos"]
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

        # Setup Chrome options for Selenium
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
        self.chrome_options.add_argument('--use-mock-keychain')
        self.chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        self.driver = None
        self.wait = None
        self._init_driver()

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
                self.driver.set_page_load_timeout(30)  # Increased timeout
                self.driver.set_script_timeout(30)  # Increased timeout
                self.wait = WebDriverWait(self.driver, 20)  # Increased wait time
                # Test the driver with a simple page
                self.driver.get("https://www.cnbc.com")
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                self.logger.info("Successfully initialized WebDriver")
                return
            except Exception as e:
                self.logger.error(f"Failed to initialize WebDriver (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
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
                self.logger.info(f"Fetching URL: {url}")
                self.driver.get(url)
                # Wait for article content to load with multiple possible selectors
                selectors = [
                    (By.CLASS_NAME, "Card-title"),
                    (By.CLASS_NAME, "Card-description"),
                    (By.CLASS_NAME, "Card-media"),
                    (By.CLASS_NAME, "Card-image"),
                    (By.CLASS_NAME, "Card-content"),
                    (By.CLASS_NAME, "Card-body"),
                    (By.CLASS_NAME, "Card-footer"),
                    (By.CLASS_NAME, "Card-header"),
                    (By.CLASS_NAME, "Card-wrapper"),
                    (By.CLASS_NAME, "Card-container"),
                    (By.CLASS_NAME, "Card-grid"),
                    (By.CLASS_NAME, "Card-row"),
                    (By.CLASS_NAME, "Card-col"),
                    (By.CLASS_NAME, "Card-box"),
                    (By.CLASS_NAME, "Card-card"),
                    (By.CLASS_NAME, "Card-panel"),
                    (By.CLASS_NAME, "Card-section"),
                    (By.CLASS_NAME, "Card-group"),
                    (By.CLASS_NAME, "Card-block"),
                    (By.CLASS_NAME, "Card-element"),
                    (By.CLASS_NAME, "Card-component"),
                    (By.CLASS_NAME, "Card-widget"),
                    (By.CLASS_NAME, "Card-module"),
                    (By.CLASS_NAME, "Card-unit"),
                    (By.CLASS_NAME, "Card-cell"),
                    (By.CLASS_NAME, "River-title"),
                    (By.CLASS_NAME, "River-description"),
                    (By.CLASS_NAME, "River-media"),
                    (By.CLASS_NAME, "River-image"),
                    (By.CLASS_NAME, "River-content"),
                    (By.CLASS_NAME, "River-body"),
                    (By.CLASS_NAME, "River-footer"),
                    (By.CLASS_NAME, "River-header"),
                    (By.CLASS_NAME, "River-wrapper"),
                    (By.CLASS_NAME, "River-container"),
                    (By.CLASS_NAME, "River-grid"),
                    (By.CLASS_NAME, "River-row"),
                    (By.CLASS_NAME, "River-col"),
                    (By.CLASS_NAME, "River-box"),
                    (By.CLASS_NAME, "River-card"),
                    (By.CLASS_NAME, "River-panel"),
                    (By.CLASS_NAME, "River-section"),
                    (By.CLASS_NAME, "River-group"),
                    (By.CLASS_NAME, "River-block"),
                    (By.CLASS_NAME, "River-element"),
                    (By.CLASS_NAME, "River-component"),
                    (By.CLASS_NAME, "River-widget"),
                    (By.CLASS_NAME, "River-module"),
                    (By.CLASS_NAME, "River-unit"),
                    (By.CLASS_NAME, "River-cell"),
                    (By.TAG_NAME, "article"),
                    (By.TAG_NAME, "body")
                ]
                found_selector = False
                for selector in selectors:
                    try:
                        self.wait.until(EC.presence_of_element_located(selector))
                        self.logger.debug(f"Found element with selector: {selector}")
                        found_selector = True
                        break
                    except:
                        continue
                if not found_selector:
                    self.logger.warning(f"No elements found with any selector for {url}")
                    # Log page source for debugging
                    self.logger.debug(f"Page source: {self.driver.page_source[:1000]}...")
                    return None

                # Additional wait for dynamic content and JavaScript execution
                time.sleep(5)
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
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
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
            # Updated selectors for article containers
            article_containers = soup.find_all(['div', 'article'], class_=re.compile('Card-title|Card-description|Card-media|Card-image|Card-content|Card-body|Card-footer|Card-header|Card-wrapper|Card-container|Card-grid|Card-row|Card-col|Card-box|Card-card|Card-panel|Card-section|Card-group|Card-block|Card-element|Card-component|Card-widget|Card-module|Card-unit|Card-cell|Card-item-wrapper|Card-item-container|Card-item-grid|Card-item-row|Card-item-col|Card-item-box|Card-item-card|Card-item-panel|Card-item-section|Card-item-group|Card-item-block|Card-item-element|Card-item-component|Card-item-widget|Card-item-module|Card-item-unit|Card-item-cell|River-title|River-description|River-media|River-image|River-content|River-body|River-footer|River-header|River-wrapper|River-container|River-grid|River-row|River-col|River-box|River-card|River-panel|River-section|River-group|River-block|River-element|River-component|River-widget|River-module|River-unit|River-cell|River-item-wrapper|River-item-container|River-item-grid|River-item-row|River-item-col|River-item-box|River-item-card|River-item-panel|River-item-section|River-item-group|River-item-block|River-item-element|River-item-component|River-item-widget|River-item-module|River-item-unit|River-item-cell'))
            
            if not article_containers:
                self.logger.warning(f"No article containers found on page {page}")
                # Log page source for debugging
                self.logger.debug(f"Page source: {soup.prettify()[:1000]}...")
                break

            for container in article_containers:
                a = container.find('a', href=True)
                if not a:
                    # Try finding link in parent elements
                    parent = container.find_parent('a', href=True)
                    if parent:
                        a = parent
                if a:
                    href = a['href']
                    if href.startswith('/'):
                        href = urljoin(self.base_url, href)
                    # Log the href for debugging
                    self.logger.debug(f"Found potential link: {href}")
                    if re.match(self.article_url_pattern, href):
                        if any(x in href.lower() for x in self.exclude_keywords):
                            self.logger.debug(f"Excluded link due to keywords: {href}")
                            continue
                        if href not in links and href not in new_links:
                            new_links.append(href)
                            self.logger.debug(f"Found article link: {href}")

            if not new_links:
                self.logger.info(f"No new links found on page {page}, stopping pagination")
                break

            links.extend(new_links)
            if page == 1:
                self.logger.info(f"First 5 links from {section_url}: {links[:5]}")
            self.logger.info(f"Total links found in {section_url} after page {page}: {len(links)}")
            
            if len(links) >= self.max_links_to_crawl:
                self.logger.info(f"Reached max links limit ({self.max_links_to_crawl})")
                break
                
            page += 1
            time.sleep(3)  # Increased delay between pages

        return links[:self.max_links_to_crawl]

    def scrape_article_content(self, url):
        """Override scrape_article_content to handle JavaScript content"""
        try:
            soup = self._get_soup(url)
            if not soup:
                return None

            # Extract title
            title_elem = soup.find('h1', class_=re.compile('article-title|headline|title|ArticleHeader-headline'))
            if not title_elem:
                title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract content
            content_elem = soup.find('div', class_=re.compile('article-body|article-content|story-body|ArticleBody-articleBody|ArticleBody-body'))
            if not content_elem:
                content_elem = soup.find('article')
            if content_elem:
                # Remove unwanted elements
                for unwanted in content_elem.find_all(['script', 'style', 'iframe', 'div.article-share', 'div.article-tags', 'div.article-related', 'div.social-share', 'div.ArticleBody-related', 'div.ArticleBody-tags', 'div.ArticleBody-share']):
                    unwanted.decompose()
                content = ' '.join([p.get_text(strip=True) for p in content_elem.find_all(['p', 'h2', 'h3', 'h4'])])
            else:
                content = None

            # Extract date
            date_elem = soup.find('time') or soup.find('span', class_=re.compile('date|timestamp|published|ArticleHeader-date'))
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

scraper = CNBCScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper.scrape_article_content

