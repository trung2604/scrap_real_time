from sources.base_scraper import BaseScraper
from urllib.parse import urljoin
import re
import logging

class CBSSportsScraper(BaseScraper):
    def __init__(self):
        article_url_pattern = r"https://www\\.cbssports\\.com/.+/(news|recap|preview)/[a-z0-9-]+/?"
        self.news_sections = [
            '/nba/', '/soccer/', '/nfl/', '/mlb/', '/tennis/', '/golf/', '/nhl/', '/mma/', '/boxing/', '/nascar/', '/wnba/', '/college-football/', '/college-basketball/'
        ]
        super().__init__("CBS Sports", "https://www.cbssports.com", article_url_pattern)
        self.max_links_to_crawl = 5000

    def _extract_links_with_pagination(self, section_url):
        links = []
        page = 1
        while len(links) < self.max_links_to_crawl:
            url = section_url if page == 1 else f"{section_url}?page={page}"
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
        for section in self.news_sections:
            section_url = urljoin(self.base_url, section)
            logging.info(f"[CBS Sports] Starting to scrape section: {section_url}")
            links = self._extract_links_with_pagination(section_url)
            logging.info(f"[CBS Sports] Found {len(links)} links in section {section}")
            if len(links) == 0:
                logging.warning(f"[CBS Sports] No article links found in section {section_url}")
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
                    logging.info(f"[CBS Sports] Successfully scraped article: {article.get('title', '')}")
                else:
                    logging.warning(f"[CBS Sports] Failed to scrape article: {link}")
        return articles

scraper = CBSSportsScraper()
scrape_all_articles = scraper.scrape_all_articles
scrape_article_content = scraper.scrape_article_content 