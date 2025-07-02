
_test_modules = {}

def get_config():
    """Lazy import config module."""
    if 'config' not in _test_modules:
        from config import get_config
        _test_modules['get_config'] = get_config
    return _test_modules['get_config']

def update_config(val):
    """Lazy import config module."""
    if 'config' not in _test_modules:
        from config import update_config
        _test_modules['update_config'] = update_config
    return _test_modules['update_config'](val)

def get_scraper():
    """Lazy import scraper module."""
    if 'scraper' not in _test_modules:
        from scrapers.website_scraper import WebsiteScraper
        _test_modules['scraper'] = WebsiteScraper
    return _test_modules['scraper']