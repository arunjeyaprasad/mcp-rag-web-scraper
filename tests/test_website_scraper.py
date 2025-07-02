import pytest
from unittest.mock import Mock, patch, AsyncMock
from playwright.async_api import Page
import config

pytestmark = pytest.mark.asyncio  # Apply to all tests in module

# Initialize the configuration before running tests
config.initialize()

# Lazy initialisation of the WebsiteScraper
from tests import get_scraper
WebsiteScraper = get_scraper()


@pytest.fixture
def mock_page():
    """Fixture to create a mock page object."""
    mock_page = AsyncMock(spec=Page)
    mock_page.title.return_value = "Test Title"
    mock_page.url = "https://example.com"
    mock_page.query_selector = AsyncMock()

    # Setup the mock element
    mock_element = AsyncMock()
    mock_element.inner_text = AsyncMock(return_value="Test content")
    mock_page.query_selector.return_value = mock_element
    return mock_page


@pytest.fixture
def mock_response():
    """Fixture to create a mock response object."""
    mock_response = Mock()
    mock_response.headers = {"last-modified": "test-date"}
    return mock_response


@pytest.fixture
def mock_document_store():
    """Fixture to create a mock DocumentStore."""
    mock_store = Mock(spec="scrapers.website_scraper.DocumentStore")
    mock_store._create_collection_if_not_exists = Mock()
    mock_store.close = Mock()
    return mock_store


@pytest.mark.asyncio
async def test_init():
    with patch('scrapers.website_scraper.DocumentStore') as doc_store:
        doc_store.return_value = mock_document_store
        scraper = WebsiteScraper("https://example.com")
        assert scraper.base_url == "https://example.com"
        assert scraper.visited_urls == set()
        assert scraper.urls_to_scrape == []
        doc_store.assert_called_once()


@pytest.mark.asyncio
async def test_can_fetch():
    with patch('scrapers.website_scraper.RobotFileParser') as mock_parser, \
      patch('scrapers.website_scraper.DocumentStore') as doc_store:
        doc_store.return_value = mock_document_store
        mock_parser.return_value.can_fetch.return_value = True
        scraper = WebsiteScraper("https://example.com")
        assert scraper._can_fetch("https://example.com/page") is True
        doc_store.assert_called_once()


@pytest.mark.asyncio
async def test_generate_content_hash():
    with patch('scrapers.website_scraper.DocumentStore') as doc_store:
        doc_store.return_value = mock_document_store
        scraper = WebsiteScraper("https://example.com")
        content = "test content"
        hash1 = scraper._generate_content_hash(content)
        hash2 = scraper._generate_content_hash(content)
        assert hash1 == hash2
        assert isinstance(hash1, str)
        doc_store.assert_called_once()


@pytest.mark.asyncio
async def test_extract_content(mock_page, mock_response):
    with patch('scrapers.website_scraper.DocumentStore') as doc_store:
        doc_store.return_value = mock_document_store
        scraper = WebsiteScraper("https://example.com")
        content = await scraper._extract_content(mock_response, mock_page)

        assert content["title"] == "Test Title"
        assert content["url"] == "https://example.com"
        assert content["content"] == "Test content"
        assert "content_hash" in content
        assert content["last_modified"] == "test-date"
        doc_store.assert_called_once()


@pytest.mark.asyncio
async def test_extract_links(mock_page):
    with patch('scrapers.website_scraper.DocumentStore') as doc_store:
        doc_store.return_value = mock_document_store
        scraper = WebsiteScraper("https://example.com")
        mock_element = AsyncMock()
        mock_element.get_attribute.return_value = "https://example.com/page"
        mock_page.query_selector_all.return_value = [mock_element]
        links = await scraper._extract_links(mock_page)

        assert links == ["https://example.com/page"]
        doc_store.assert_called_once()


@pytest.mark.asyncio
async def test_progress():
    with patch('scrapers.website_scraper.DocumentStore') as doc_store:
        doc_store.return_value = mock_document_store
        scraper = WebsiteScraper("https://example.com")
        scraper.visited_urls.add("https://example.com/page1")
        scraper.urls_to_scrape.append("https://example.com/page2")

        progress = scraper.progress()
        assert progress["visited_urls"] == 1
        assert progress["remaining_urls"] == 1
        doc_store.assert_called_once()


@pytest.mark.asyncio
async def test_stop():
    with patch('scrapers.website_scraper.DocumentStore') as doc_store:
        mock_store = mock_document_store
        doc_store.return_value = mock_store
        mock_store.close = Mock(return_value=None)
        scraper = WebsiteScraper("https://example.com")
        scraper.visited_urls.add("https://example.com/page")
        scraper.urls_to_scrape.append("https://example.com/page2")
        scraper.stop()

        assert len(scraper.visited_urls) == 0
        assert len(scraper.urls_to_scrape) == 0
        doc_store.assert_called_once()
        mock_store.close.assert_called_once()
