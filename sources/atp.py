from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
from bs4 import BeautifulSoup

class ATP:
    def __init__(self):
        # Configure logging
        self.logger = logging.getLogger('ATP')
        self.logger.setLevel(logging.INFO)
        # Create console handler with formatting
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def _get_soup(self, url):
        """Get BeautifulSoup object using Selenium for JavaScript content with SSL verification and retry logic"""
        max_retries = 3
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                if not self.driver:
                    self._init_driver()
                # Create new options for each request to enable JavaScript
                chrome_options = Options()
                chrome_options.add_argument('--headless')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-infobars')
                chrome_options.add_argument('--disable-notifications')
                chrome_options.add_argument('--disable-popup-blocking')
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                chrome_options.add_argument('--disable-images')  # Disable images to speed up loading
                chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # Disable images in Blink
                chrome_options.add_argument('--disk-cache-size=1')  # Minimize disk cache
                chrome_options.add_argument('--media-cache-size=1')  # Minimize media cache
                chrome_options.add_argument('--disable-application-cache')  # Disable application cache
                chrome_options.add_argument('--disable-cache')  # Disable browser cache
                chrome_options.add_argument('--disable-offline-load-stale-cache')  # Disable offline cache
                chrome_options.add_argument('--disable-background-networking')  # Disable background networking
                chrome_options.add_argument('--disable-default-apps')  # Disable default apps
                chrome_options.add_argument('--disable-sync')  # Disable sync
                chrome_options.add_argument('--disable-translate')  # Disable translate
                chrome_options.add_argument('--metrics-recording-only')  # Disable metrics recording
                chrome_options.add_argument('--no-first-run')  # Disable first run
                chrome_options.add_argument('--safebrowsing-disable-auto-update')  # Disable safebrowsing
                chrome_options.add_argument('--password-store=basic')  # Disable password store
                chrome_options.add_argument('--use-mock-keychain')  # Use mock keychain
                chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')
                chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                
                # Reinitialize driver with new options
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.set_page_load_timeout(20)  # Standardized timeout
                self.driver.set_script_timeout(20)  # Standardized timeout
                self.wait = WebDriverWait(self.driver, 15)  # Standardized wait time
                
                # Add proxy support if configured
                if hasattr(self, 'proxy') and self.proxy:
                    self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.headers["User-Agent"]})
                    self.driver.execute_cdp_cmd('Network.enable', {})
                    self.driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {"headers": self.headers})
                
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
                    (By.TAG_NAME, "body")
                ]
                for selector in selectors:
                    try:
                        self.wait.until(EC.presence_of_element_located(selector))
                        break
                    except:
                        continue
                # Additional wait for dynamic content and JavaScript execution
                time.sleep(5)
                if not '/news/' in url or url.endswith('/news/'):
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