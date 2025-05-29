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
        self.news_sections = [
            '/news/news',  # Main news section
            '/news/business',  # Business news
            '/news/tech',  # Tech news
            '/news/travel',  # Travel news
            '/news/life',  # Life news
            '/news/sports',  # Sports news
            '/news/world',  # World news
            '/news/perspectives'  # Perspectives
        ]
        super().__init__("VnExpress International", "https://e.vnexpress.net", article_url_pattern)
        self.max_links_to_crawl = 200

    def scrape_all_articles(self):
        articles = []
        today = datetime.utcnow().date()
        logging.info(f"[VnExpress] Starting to scrape articles for date: {today}")

        for section in self.news_sections:
            try:
                section_url = urljoin(self.base_url, section)
                logging.info(f"[VnExpress] Processing section: {section_url}")
                soup = self._get_soup(section_url)
                if not soup:
                    logging.error(f"[VnExpress] Failed to get soup for section: {section_url}")
                    continue

                links = self._extract_links(soup, section_url)
                logging.info(f"[VnExpress] Found {len(links)} links in section {section}")
                
                for link in links:
                    try:
                        logging.info(f"[VnExpress] Scraping article: {link}")
                        article = self.scrape_article_content(link)
                        if article:
                            if article.get('published_at'):
                                pub_date = article['published_at'].date()
                                logging.info(f"[VnExpress] Article date: {pub_date} for {link}")
                                if pub_date == today:  # Only include today's articles
                                    articles.append(article)
                                    logging.info(f"[VnExpress] Added article to list: {link}")
                                    logging.info(f"[VnExpress] Current article count: {len(articles)}")
                                    if len(articles) >= 10:
                                        logging.info("[VnExpress] Reached 10 articles limit, stopping")
                                        return articles
                            else:
                                logging.warning(f"[VnExpress] Article has no published date: {link}")
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

    def _extract_links(self, soup, base_url):
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('/'):
                href = urljoin(self.base_url, href)
            if re.match(self.article_url_pattern, href):
                if href not in links:
                    links.append(href)
                    if len(links) >= self.max_links_to_crawl:
                        break
        return links

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
