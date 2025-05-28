from news_scraper_backend.sources.base_scraper import BaseScraper
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
            '/news', '/business', '/tech', '/travel', '/life', '/sports', '/world', '/perspectives'
        ]
        super().__init__("VnExpress International", "https://e.vnexpress.net", article_url_pattern)
        self.max_links_to_crawl = 200

    def scrape_all_articles(self):
        articles = []
        today = datetime.utcnow().date()

        for section in self.news_sections:
            try:
                section_url = urljoin(self.base_url, section)
                soup = self._get_soup(section_url)
                if not soup:
                    continue

                links = self._extract_links(soup, section_url)
                for link in links:
                    try:
                        article = self.scrape_article_content(link)
                        if article and article.get('published_at'):
                            pub_date = article['published_at'].date()
                            if pub_date == today:  # Only include today's articles
                                articles.append(article)
                                logging.info(f"[VnExpress] Found today's article: {link} ({pub_date})")
                                if len(articles) >= 10:
                                    return articles
                    except Exception as e:
                        logging.error(f"[VnExpress] Error scraping {link}: {e}")
                        continue
            except Exception as e:
                logging.error(f"[VnExpress] Error processing section {section}: {e}")
                continue

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
        result = super().scrape_article_content(url)
        if result:
            if "e.vnexpress.net" not in url.lower():
                import logging
                logging.warning(f"Invalid VnExpress URL: {url}")
                return None
        return result

scraper = VnExpressScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper.scrape_article_content 
