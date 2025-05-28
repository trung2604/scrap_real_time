import logging
import json
from pathlib import Path
import sys
import os
import importlib
from datetime import datetime, timedelta
import random
import requests
import codecs

# Thêm thư mục cha vào Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Sử dụng absolute import thay vì relative import
from database import save_article, get_scraping_stats
from utils import fetch_url
from sources.skysports import scrape_all_articles as scrape_skysports
from sources.cnbc import scrape_all_articles as scrape_cnbc
from sources.vnexpress import scrape_all_articles as scrape_vnexpress

# Cấu hình logging với UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_scrape.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Đảm bảo luôn có handler ra console (stdout)
if not any(isinstance(h, logging.StreamHandler) for h in logging.getLogger().handlers):
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(console_handler)

# Đảm bảo stdout sử dụng UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

def check_url_access(url):
    """Kiểm tra xem URL có truy cập được không"""
    try:
        logging.info(f"Kiểm tra URL: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        logging.info(f"Mã trạng thái: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Lỗi khi truy cập URL {url}: {str(e)}")
        return False

def process_news_source(source_config):
    logging.info(f"\n{'='*50}")
    logging.info(f"Xử lý nguồn tin: {source_config['name']}")
    logging.info(f"{'='*50}")

    # Kiểm tra URL cơ sở
    if not check_url_access(source_config['base_url']):
        logging.error(f"Không thể truy cập URL cơ sở của {source_config['name']}")
        return False

    try:
        # Nhập module scraper tương ứng
        logging.info(f"Nhập module: sources.{source_config['module']}")
        module = importlib.import_module(f"sources.{source_config['module']}")

        # Scrape tất cả bài báo để chọn ngẫu nhiên
        logging.info(f"Scrape bài báo từ {source_config['name']} để kiểm tra ngẫu nhiên")
        articles = module.scrape_all_articles()

        if not articles:
            logging.warning(f"Không tìm thấy bài báo nào cho {source_config['name']}")
            return False

        today = datetime.utcnow().date()
        today_articles = []
        for article in articles:
            pub_date = article.get('published_at')
            if pub_date:
                # Loại bỏ múi giờ để đảm bảo so sánh offset-naive
                pub_date = pub_date.replace(tzinfo=None)
                if pub_date.date() == today:
                    today_articles.append(article)

        if not today_articles:
            logging.warning(f"Không tìm thấy bài báo nào đăng hôm nay cho {source_config['name']}")
            return False

        # Chọn ngẫu nhiên một bài báo
        random_article = random.choice(today_articles)
        logging.info(f"Bài báo ngẫu nhiên: {random_article['title']} ({random_article['url']})")
        random_article_date = random_article['published_at'].replace(tzinfo=None)
        logging.info(f"Ngày đăng: {random_article_date}")

        # Kiểm tra xem bài báo có đăng hôm nay không
        if random_article_date.date() == today:
            logging.info(f"Kiểm tra thành công: Bài báo ngẫu nhiên được đăng hôm nay ({today})")
            if save_article(random_article):
                logging.info(f"Lưu bài báo ngẫu nhiên thành công: {random_article['title']}")
            else:
                logging.info(f"Bài báo ngẫu nhiên đã tồn tại trong cơ sở dữ liệu: {random_article['url']}")

            # Scrape toàn bộ bài báo trong ngày hiện tại
            logging.info(f"Bắt đầu scrape toàn bộ bài báo trong ngày hiện tại cho {source_config['name']}")
            articles_saved = 0
            for article in today_articles:
                try:
                    if article['url'] == random_article['url']:
                        continue  # Bỏ qua bài báo ngẫu nhiên đã lưu
                    logging.info(f"Xử lý bài báo: {article['title']} ({article['url']})")
                    if save_article(article):
                        articles_saved += 1
                        logging.info(f"Lưu bài báo thành công: {article['title']}")
                    else:
                        logging.info(f"Bài báo đã tồn tại trong cơ sở dữ liệu: {article['url']}")
                except Exception as e:
                    logging.error(f"Lỗi khi xử lý bài báo {article.get('url', 'unknown')}: {str(e)}")
                    continue

            logging.info(f"Hoàn tất scrape {source_config['name']}. Lưu {articles_saved} bài báo mới đăng hôm nay.")
            return True
        else:
            logging.error(f"Kiểm tra thất bại: Bài báo ngẫu nhiên không được đăng hôm nay ({random_article_date.date()})")
            return False

    except Exception as e:
        logging.error(f"Lỗi khi xử lý {source_config['name']}: {str(e)}")
        return False

def run_scraper():
    try:
        # Tải cấu hình nguồn
        config_path = Path(__file__).parent / "config.json"
        logging.info(f"Tải cấu hình từ: {config_path}")
        with open(config_path) as f:
            sources = json.load(f)

        logging.info(f"Tìm thấy {len(sources)} nguồn để xử lý")

        # Lấy ngẫu nhiên 3 domain
        random_sources = random.sample(sources, min(3, len(sources)))

        # Lấy thống kê trước khi scrape
        stats_before = get_scraping_stats()
        logging.info(f"Thống kê trước khi scrape: {stats_before}")

        # Chỉ kiểm tra 1 bài đăng hôm nay cho mỗi domain
        for source in random_sources:
            logging.info(f"\n{'='*50}")
            logging.info(f"Xử lý nguồn tin: {source['name']}")
            logging.info(f"{'='*50}")

            # Kiểm tra URL cơ sở
            if not check_url_access(source['base_url']):
                logging.error(f"Không thể truy cập URL cơ sở của {source['name']}")
                continue

            try:
                # Nhập module scraper tương ứng
                logging.info(f"Nhập module: sources.{source['module']}")
                module = importlib.import_module(f"sources.{source['module']}")

                # Scrape tất cả bài báo để chọn ngẫu nhiên
                logging.info(f"Scrape bài báo từ {source['name']} để kiểm tra ngẫu nhiên")
                articles = module.scrape_all_articles()

                if not articles:
                    logging.warning(f"Không tìm thấy bài báo nào cho {source['name']}")
                    continue

                today = datetime.utcnow().date()
                today_articles = []
                for article in articles:
                    pub_date = article.get('published_at')
                    if pub_date:
                        pub_date = pub_date.replace(tzinfo=None)
                        if pub_date.date() == today:
                            today_articles.append(article)

                if not today_articles:
                    logging.warning(f"Không tìm thấy bài báo nào đăng hôm nay cho {source['name']}")
                    continue

                # Chọn ngẫu nhiên một bài báo
                random_article = random.choice(today_articles)
                logging.info(f"Bài báo ngẫu nhiên: {random_article['title']} ({random_article['url']})")
                random_article_date = random_article['published_at'].replace(tzinfo=None)
                logging.info(f"Ngày đăng: {random_article_date}")

                # Kiểm tra xem bài báo có đăng hôm nay không
                if random_article_date.date() == today:
                    logging.info(f"Kiểm tra thành công: Bài báo ngẫu nhiên được đăng hôm nay ({today})")
                    if save_article(random_article):
                        logging.info(f"Lưu bài báo ngẫu nhiên thành công: {random_article['title']}")
                    else:
                        logging.info(f"Bài báo ngẫu nhiên đã tồn tại trong cơ sở dữ liệu: {random_article['url']}")
                else:
                    logging.error(f"Kiểm tra thất bại: Bài báo ngẫu nhiên không được đăng hôm nay ({random_article_date.date()})")

            except Exception as e:
                logging.error(f"Lỗi khi xử lý {source['name']}: {str(e)}")
                continue

        # Lấy thống kê sau khi scrape
        stats_after = get_scraping_stats()
        logging.info(f"Thống kê sau khi scrape: {stats_after}")

    except Exception as e:
        logging.error(f"Lỗi nghiêm trọng: {str(e)}")

if __name__ == "__main__":
    run_scraper()