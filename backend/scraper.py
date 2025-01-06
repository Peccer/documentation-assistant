import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging

def is_relative_url(url):
    """Checks if a URL is relative"""
    parsed_url = urlparse(url)
    return not parsed_url.scheme

def is_same_domain(base_url, url):
    """Check if both URLs have the same domain."""
    base_domain = urlparse(base_url).netloc
    url_domain = urlparse(url).netloc
    return base_domain == url_domain


def get_links_from_page(base_url, page_url):
    """Gets all valid links from a page."""
    try:
        response = requests.get(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        links = [a.get("href") for a in soup.find_all("a") if a.get("href")]

        full_links = []
        for link in links:
           if is_relative_url(link):
               full_link = urljoin(base_url, link)
           else:
              full_link = link
           if is_same_domain(base_url, full_link):
              full_links.append(full_link)
        return list(set(full_links))
    except requests.exceptions.RequestException as e:
         logging.error(f"Error fetching {page_url}: {e}")
         return []

def extract_text_from_page(page_url):
    """Extracts text from a page."""
    try:
        response = requests.get(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        # You might need to fine-tune this depending on the website's structure
        text = " ".join(p.get_text() for p in soup.find_all("p")) # This might need a more custom approach
        text += " ".join(h.get_text() for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
        return text.strip()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {page_url}: {e}")
        return ""

def scrape_documentation(base_url, max_pages=10):
    """Crawls and scrapes documentation."""
    visited = set()
    to_visit = [base_url]
    scraped_data = {}
    
    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
             continue
        logging.info(f"Scraping {url}")
        
        visited.add(url)
        text = extract_text_from_page(url)
        if text:
            scraped_data[url] = text
        
        links = get_links_from_page(base_url, url)
        for link in links:
            if link not in visited:
                to_visit.append(link)
    logging.info(f"Scraped {len(visited)} pages.")
    return scraped_data