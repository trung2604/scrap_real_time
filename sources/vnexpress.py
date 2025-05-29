from sources.base_scraper import BaseScraper
from datetime import datetime, timedelta
import logging
from urllib.parse import urljoin
import re

class VnExpressScraper(BaseScraper):
    def __init__(self):
        today = datetime.utcnow().date()
        # Chỉ lấy link có ngày hôm nay trong URL (VnExpress không có ngày trong URL, nên vẫn lọc theo chuyên mục)
        article_url_pattern = r"https://e\.vnexpress\.net/news/.+"
        self.max_links_to_crawl = 3000
        self.news_sections = [
            '/news/sports',
            '/news/football',
            '/news/tennis',
            '/news/golf',
            '/news/othersports',
            # Thêm các chuyên mục con thể thao khác nếu có
        ]
        super().__init__("VnExpress International", "https://e.vnexpress.net", article_url_pattern)

    def _extract_links_with_pagination(self, section_url):
        links = []
        page = 1
        while len(links) < self.max_links_to_crawl:
            url = f"{section_url}?page={page}"
            soup = self._get_soup(url)
            if not soup:
                break
            new_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/'):
                    href = urljoin(self.base_url, href)
                if re.match(self.article_url_pattern, href):
                    if href not in links and href not in new_links:
                        new_links.append(href)
            if not new_links:
                break
            links.extend(new_links)
            if len(links) >= self.max_links_to_crawl:
                break
            page += 1
        return links[:self.max_links_to_crawl]

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

    def scrape_article_content(self, url):
        logging.info(f"[VnExpress] Starting to scrape content for: {url}")
        result = super().scrape_article_content(url)
        if result:
            if "e.vnexpress.net" not in url.lower():
                logging.warning(f"[VnExpress] Invalid VnExpress URL: {url}")
                return None
            logging.info(f"[VnExpress] Successfully scraped article: {url}")
            logging.info(f"[VnExpress] Article title: {result.get('title', 'no title')}")
            logging.info(f"[VnExpress] Article date: {result.get('published_at', 'no date')}")
            logging.info(f"[VnExpress] Content length: {len(result.get('content', ''))} characters")
        else:
            logging.warning(f"[VnExpress] Failed to scrape article content: {url}")
        return result

scraper = VnExpressScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper.scrape_article_content 
