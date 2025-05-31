from sources.base_scraper import BaseScraper
from datetime import datetime, timedelta
import logging
from urllib.parse import urljoin
import re
import requests
from bs4 import BeautifulSoup
import time
import certifi
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class VnExpressScraper(BaseScraper):
    def __init__(self):
        # VnExpress có dạng link bài báo:
        # - https://e.vnexpress.net/news/sports/title-article-1234567.html
        # - https://e.vnexpress.net/news/football/title-article-1234567.html
        # - https://e.vnexpress.net/news/tennis/title-article-1234567.html
        article_url_pattern = r"https://e\.vnexpress\.net/news/(?:sports|football|tennis|golf|othersports)/[a-z0-9-]+-\d+\.html"
        self.news_sections = [
            '/news/sports', '/news/football', '/news/tennis', '/news/golf', '/news/othersports'
        ]
        super().__init__("VnExpress International", "https://e.vnexpress.net", article_url_pattern)
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
        """Override _get_soup to add custom headers and SSL verification"""
        try:
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logging.error(f"[VnExpress] Error fetching {url}: {e}")
            return None

    def _extract_links_with_pagination(self, section_url):
        links = []
        page = 1
        while len(links) < self.max_links_to_crawl:
            url = f"{section_url}?page={page}"
            logging.info(f"[VnExpress] Fetching page {page} from {url}")
            soup = self._get_soup(url)
            if not soup:
                logging.warning(f"[VnExpress] Could not fetch page {page} from {url}")
                break
            new_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/'):
                    href = urljoin(self.base_url, href)
                if re.match(self.article_url_pattern, href):
                    if href not in links and href not in new_links:
                        new_links.append(href)
                        logging.debug(f"[VnExpress] Found article link: {href}")
            if not new_links:
                logging.info(f"[VnExpress] No new links found on page {page}, stopping pagination")
                break
            links.extend(new_links)
            if page == 1:
                logging.info(f"[VnExpress] First 5 links from {section_url}: {links[:5]}")
            logging.info(f"[VnExpress] Total links found in {section_url} after page {page}: {len(links)}")
            if len(links) >= self.max_links_to_crawl:
                logging.info(f"[VnExpress] Reached max links limit ({self.max_links_to_crawl})")
                break
            page += 1
        return links[:self.max_links_to_crawl]

    def scrape_article_content(self, url):
        """Override scrape_article_content to add custom headers"""
        try:
            article = super().scrape_article_content(url)
            if article:
                # Verify the article has required fields
                if not article.get('title') or not article.get('content'):
                    logging.warning(f"[VnExpress] Article missing required fields: {url}")
                    return None
                return article
            return None
        except Exception as e:
            logging.error(f"[VnExpress] Error scraping article {url}: {e}")
            return None

    def scrape_all_articles(self):
        articles = []
        logging.info(f"[VnExpress] Starting to scrape all articles (no date filter)")

        for section in self.news_sections:
            try:
                section_url = urljoin(self.base_url, section)
                logging.info(f"[VnExpress] Processing section: {section_url}")
                links = self._extract_links_with_pagination(section_url)
                logging.info(f"[VnExpress] Found {len(links)} links in section {section}")
                for link in links:
                    try:
                        logging.info(f"[VnExpress] Scraping article: {link}")
                        article = self.scrape_article_content(link)
                        if article:
                            articles.append({
                                'title': article.get('title', ''),
                                'content': article.get('content', ''),
                                'url': link,
                                'published_at': article.get('published_at').isoformat() + 'Z' if article.get('published_at') else None,
                                'source': self.source_name
                            })
                            logging.info(f"[VnExpress] Added article to list: {link}")
                            logging.info(f"[VnExpress] Current article count: {len(articles)}")
                        else:
                            logging.warning(f"[VnExpress] Failed to scrape article: {link}")
                    except Exception as e:
                        logging.error(f"[VnExpress] Error scraping {link}: {e}")
                        continue
            except Exception as e:
                logging.error(f"[VnExpress] Error processing section {section}: {e}")
                continue

        logging.info(f"[VnExpress] Finished scraping. Total articles found: {len(articles)}")
        return articles

scraper = VnExpressScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper.scrape_article_content 
