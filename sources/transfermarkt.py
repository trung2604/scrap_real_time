from sources.base_scraper import BaseScraper
from urllib.parse import urljoin
import re
import logging

class TransfermarktScraper(BaseScraper):
    def __init__(self):
        # Transfermarkt có dạng link bài báo:
        # - https://www.transfermarkt.com/news/view/news/123456
        # - https://www.transfermarkt.com/transfers/news/view/news/123456
        # Nới lỏng pattern để khớp nhiều dạng link hơn
        article_url_pattern = r"https://www\\.transfermarkt\\.com/(?:transfers/)?news/(?:view/)?news/\\d+"
        self.news_sections = [
            '/transfers/news/', '/news/', '/rumours/', '/statistics/', '/international/'
        ]
        super().__init__("Transfermarkt", "https://www.transfermarkt.com", article_url_pattern)
        self.max_links_to_crawl = 5000

    def _extract_links_with_pagination(self, section_url):
        links = []
        page = 1
        while len(links) < self.max_links_to_crawl:
            # Transfermarkt dùng ?page=2, ?page=3, etc cho phân trang
            url = section_url if page == 1 else f"{section_url}?page={page}"
            logging.info(f"[Transfermarkt] Fetching page {page} from {url}")
            soup = self._get_soup(url)
            if not soup:
                logging.warning(f"[Transfermarkt] Could not fetch page {page} from {url}")
                break
            new_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/'):
                    href = urljoin(self.base_url, href)
                if re.match(self.article_url_pattern, href):
                    if href not in links and href not in new_links:
                        new_links.append(href)
                        logging.debug(f"[Transfermarkt] Found article link: {href}")
            if not new_links:
                logging.info(f"[Transfermarkt] No new links found on page {page}, stopping pagination")
                break
            links.extend(new_links)
            if page == 1:
                logging.info(f"[Transfermarkt] First 5 links from {section_url}: {links[:5]}")
            logging.info(f"[Transfermarkt] Total links found in {section_url} after page {page}: {len(links)}")
            if len(links) >= self.max_links_to_crawl:
                logging.info(f"[Transfermarkt] Reached max links limit ({self.max_links_to_crawl})")
                break
            page += 1
        return links[:self.max_links_to_crawl]

    def scrape_all_articles(self):
        articles = []
        for section in self.news_sections:
            section_url = urljoin(self.base_url, section)
            logging.info(f"[Transfermarkt] Starting to scrape section: {section_url}")
            links = self._extract_links_with_pagination(section_url)
            logging.info(f"[Transfermarkt] Found {len(links)} links in section {section}")
            if len(links) == 0:
                logging.warning(f"[Transfermarkt] No article links found in section {section_url}")
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
                    logging.info(f"[Transfermarkt] Successfully scraped article: {article.get('title', '')}")
                else:
                    logging.warning(f"[Transfermarkt] Failed to scrape article: {link}")
        return articles

scraper = TransfermarktScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper.scrape_article_content 