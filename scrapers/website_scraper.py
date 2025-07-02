import hashlib
import asyncio
from datetime import datetime
from typing import List, Dict
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin
from config import config
from playwright.async_api import async_playwright

from storage.document_store import DocumentStore

# Constants
DEFAULT_USER_AGENT = config.get_scraper_useragent()
DEFAULT_CRAWL_DELAY = config.get_config()["SCRAPE_CONFIGURATION"].get("crawl_delay", 2)  # Default crawl delay in seconds 
DEFAULT_MAX_PAGES = config.get_config()["SCRAPE_CONFIGURATION"].get("max_pages", 200)  # Default maximum pages to scrape
MAX_CONCURRENT_PAGES = config.get_config()["SCRAPE_CONFIGURATION"].get("concurrency", 25)  # Default number of concurrent requests


class WebsiteScraper:
    def __init__(self, base_url: str, user_agent: str = DEFAULT_USER_AGENT, collection_name: str = "website_content", override_robots: bool = False):
        self.logger = config.get_logger(__name__)
        self.document_store = DocumentStore(collection_name=collection_name)
        self.scraper_id = collection_name
        self.base_url = base_url
        self.user_agent = user_agent
        self.visited_urls = set()
        self.urls_to_scrape = []
        self.override_robots = override_robots
        self.robots_parser = self._setup_robots_parser()
        self.semaphore = None
        self.stop_triggered = False
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)
        self.last_scraped_time = None

    def _setup_robots_parser(self) -> RobotFileParser:
        """
            Setup and fetch robots.txt rules
            Returns:
                RobotFileParser: Parsed robots.txt rules
        """
        parser = RobotFileParser()
        robots_url = urljoin(self.base_url, "/robots.txt")
        parser.set_url(robots_url)
        try:
            parser.read()
            self.logger.info(f"Successfully parsed robots.txt from {robots_url}")
        except Exception as e:
            self.logger.warning(f"Could not fetch robots.txt: {str(e)}")
        return parser

    def _can_fetch(self, url: str) -> bool:
        """
            Check if URL is allowed to be scraped. If override_robots is True, always allow scraping.
            Args:
                url (str): URL to check
            Returns:
                bool: True if scraping is allowed, False otherwise
        """
        try:
            if self.override_robots or not self.robots_parser:
                self.logger.debug(f"Override robots.txt for {url}")
                return True
            return self.robots_parser.can_fetch(self.user_agent, url)
        except Exception:
            # If robots.txt check fails, assume conservative approach
            return False

    async def scrape_website(self, max_pages: int = DEFAULT_MAX_PAGES):
        """
            Scrape website and store content
            Args:
                max_pages (int): Maximum number of pages to scrape
        """
        self.last_scraped_time = datetime.now()
        self.visited_urls.clear()
        self.logger.info(f"Starting scrape for {self.base_url} with max pages: {max_pages}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # Create a new browser context with custom user agent
            self.logger.info(f"Using user agent: {self.user_agent}")
            self.logger.info(f"Using crawl delay: {DEFAULT_CRAWL_DELAY} seconds")
            context = await browser.new_context(
                user_agent=self.user_agent,
                viewport={'width': 1920, 'height': 1080}
            )

            self.logger.info(f"Browser context created with user agent: {self.user_agent}")

            try:
                crawl_delay = self.robots_parser.crawl_delay(self.user_agent)
                if crawl_delay is None:
                    crawl_delay = DEFAULT_CRAWL_DELAY

                # Start with the base URL
                self.urls_to_scrape = [self.base_url]
                first_run = True
                while self.urls_to_scrape and len(self.visited_urls) < max_pages:
                    # Process URLs concurrently in batches
                    if not first_run:
                        batch = self.urls_to_scrape[:MAX_CONCURRENT_PAGES]
                        self.urls_to_scrape = self.urls_to_scrape[MAX_CONCURRENT_PAGES:]
                    else:
                        batch = self.urls_to_scrape
                        first_run = False

                    self.logger.info(f"URLs to scrape: {len(self.urls_to_scrape)}, Visited: {len(self.visited_urls)}")

                    # Create tasks for concurrent scraping
                    tasks = [
                        self._scrape_page_with_semaphore(
                            context, url, 
                            max_pages, crawl_delay)
                        for url in batch
                        if url not in self.visited_urls and self._can_fetch(url)
                    ]

                    self.logger.info(f"Starting batch scrape for {len(tasks)} URLs")
                    # Wait for batch to complete
                    await asyncio.gather(*tasks)

            except Exception as e:
                self.logger.error(f"Error during scraping: {str(e)}")
            finally:
                await context.close()
                await browser.close()

    async def _scrape_page_with_semaphore(self, context, url: str,
                                          max_pages: int, crawl_delay: float):
        """
            Wrapper to handle semaphore for concurrent page scraping
            Args:
                context: Playwright browser context
                url (str): URL to scrape
                max_pages (int): Maximum number of pages to scrape
                crawl_delay (float): Delay between requests
        """
        async with self.semaphore:
            await self._scrape_page(context, url, max_pages, crawl_delay)

    async def _scrape_page(self, context, url: str,
                           max_pages: int, crawl_delay: float):
        """
            Scrape a single page.
            Returns immediately if the URL has already been visited.
            This method is responsible for navigating to the page,
            extracting content, and finding new links.
            Args:
                context: Playwright browser context
                url (str): URL to scrape
                max_pages (int): Maximum number of pages to scrape
                crawl_delay (float): Delay between requests
        """
        if url in self.visited_urls:
            return

        try:
            self.logger.info(f"Scraping: {url}")
            page = await context.new_page()

            try:
                response = await page.goto(url, wait_until="networkidle")
                await asyncio.sleep(crawl_delay)

                self.visited_urls.add(url)

                content = await self._extract_content(response, page)
                if content:
                    self.document_store.store_documents([content])

                # Find and follow allowed links
                new_links = await self._extract_links(page)
                self.urls_to_scrape.extend([
                    link for link in new_links 
                    if (link not in self.visited_urls and 
                        link not in self.urls_to_scrape and 
                        self._can_fetch(link))
                ])
            except asyncio.exceptions.CancelledError as ce:
                self.logger.error(f"Cancelled the scraping for {url}: {ce}")
            finally:
                await page.close()

        except Exception as e:
            self.logger.error(f"Error scraping {url}: {e}")

    async def _extract_content(self, response, page) -> Dict:
        """
            Extract content from page
            Args:
                response: Playwright response object
                page: Playwright page object
            Returns:
                Dict: Extracted content with URL, title, and text
        """
        try:
            title = await page.title()
            # Try specific content containers first
            main_content = await page.query_selector("main[id*='article'], main[id*='content'], main[class*='article'], main[class*='content'], [role='main']")
            if main_content:
                content_text = await main_content.inner_text()
            else:
                # Fall back to body content, excluding navigation and footer
                body_content = await page.query_selector("body")
                if body_content:
                    # Remove common non-content elements
                    for selector in ["nav", "header", "footer", "#footer", "#header", ".navigation", ".menu", ".sidebar"]:
                        elements = await page.query_selector_all(selector)
                        for element in elements:
                            await element.evaluate('node => node.remove()')
                    content_text = await body_content.inner_text()
                else:
                    content_text = ""
            # print(f"Extracted content from {page.url}: {content_text[:1000]}...")  # Log first 100 chars for debugging
            # Log content length for debugging
            self.logger.debug(f"Extracted content length from {page.url}: {len(content_text)}")
            return {
                "url": page.url,
                "title": title,
                "content": content_text,
                "content_hash": self._generate_content_hash(content_text),
                "last_modified": response.headers.get("last-modified", None),
                "metadata": {
                    "scraped_at": str(datetime.now())
                }
            }
        except Exception as e:
            self.logger.error(f"Error extracting content: {str(e)}")
            return None

    async def _extract_links(self, page) -> List[str]:
        """
            Extract links from page
            Args:
                page: Playwright page object
            Returns:
                List[str]: List of absolute URLs found on the page
        """
        links = []
        elements = await page.query_selector_all("a[href]")

        for element in elements:
            href = await element.get_attribute("href")
            if not href:
                continue
            if href and href.startswith(self.base_url):
                links.append(href)
            elif href and href.startswith("/"):
                # Handle relative links
                full_url = urljoin(self.base_url, href)
                links.append(full_url)
        return links

    def _generate_content_hash(self, content: str) -> str:
        """
            Generate SHA-256 hash of content for change detection
            Args:
                content (str): Content to hash
            Returns:
                str: SHA-256 hash of the content
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def stop(self):
        """
            Stop the scraper and scheduler
        """
        self.logger.info("Stopping website scraper")
        self.stop_triggered = True
        self.visited_urls.clear()
        self.urls_to_scrape.clear()
        self.document_store.close()

    def progress(self):
        """
            Get current progress of the scraper
            Returns:
                Dict: Current progress with visited and remaining URLs
        """
        return {
            "visited_urls": len(self.visited_urls),
            "remaining_urls": len(self.urls_to_scrape),
            "last_scraped_time": self.last_scraped_time.isoformat() if self.last_scraped_time else None,
        }

    def get_scraper_id(self) -> str:
        """
            Get the unique ID for this scraper instance
            Returns:
                str: Unique ID for the scraper
        """
        return self.scraper_id
