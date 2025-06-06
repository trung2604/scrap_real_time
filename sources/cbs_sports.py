import logging
import time
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import dateutil.parser

class CBSSportsScraper(BaseScraper):
    def __init__(self):
        # Configure logging
        self.logger = logging.getLogger('CBS Sports')
        self.logger.setLevel(logging.INFO)
        # Create console handler with formatting
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # ... existing initialization code ...

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
                self.driver.get("https://www.cbssports.com")
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
                # ... existing chrome options code ...
                
                self.driver.get(url)
                # ... existing selectors and wait code ...
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