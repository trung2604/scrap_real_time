import logging
import time
from functools import wraps
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='scraper.log'
)

def rate_limit(seconds):
    def decorator(func):
        last_called = {}
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            if func.__name__ not in last_called or \
               current_time - last_called[func.__name__] >= seconds:
                last_called[func.__name__] = current_time
                return func(*args, **kwargs)
            else:
                time.sleep(seconds - (current_time - last_called[func.__name__]))
                last_called[func.__name__] = time.time()
                return func(*args, **kwargs)
        return wrapper
    return decorator

def fetch_url(url, max_retries=3, retry_delay=1):
    """Fetch URL with retry mechanism and proper headers"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }

    for attempt in range(max_retries):
        try:
            logging.info(f"Fetching URL: {url} (attempt {attempt + 1}/{max_retries})")
            response = requests.get(url, headers=headers, timeout=10)
            
            # Log response details
            logging.info(f"Response status: {response.status_code}")
            logging.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 403:
                logging.error(f"Access forbidden (403) for URL: {url}")
                logging.error(f"Response content: {response.text[:500]}...")  # Log first 500 chars
                return None
                
            response.raise_for_status()
            
            # Check if content is JavaScript-rendered
            content_type = response.headers.get('Content-Type', '')
            logging.info(f"Content-Type: {content_type}")
            
            if 'text/javascript' in content_type:
                logging.warning(f"URL {url} returns JavaScript content, may need Selenium")
                return None
                
            # Log content length
            content_length = len(response.text)
            logging.info(f"Content length: {content_length} characters")
            
            if content_length < 100:  # Suspiciously small content
                logging.warning(f"Suspiciously small content ({content_length} chars) for URL: {url}")
                logging.warning(f"Content preview: {response.text[:200]}...")
                
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Check if we got a valid HTML document
            if not soup.find('html'):
                logging.warning(f"No HTML document found in response for URL: {url}")
                logging.warning(f"Content preview: {response.text[:200]}...")
                return None
                
            return soup
            
        except requests.RequestException as e:
            logging.error(f"Error fetching {url} (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                return None
        except Exception as e:
            logging.error(f"Unexpected error fetching {url}: {str(e)}")
            return None
