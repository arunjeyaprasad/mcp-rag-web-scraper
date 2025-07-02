import os
import json
import logging
from dotenv import load_dotenv

__default__config = dict(
    # Default configuration settings
    logging_level=logging.INFO,  # Default logging level
    server_port=8090,            # Default server port
    llm_model="gemma3:12b"
)

__default_scrape_config = {
    # Default scraping configuration
    "user_agent": "Mozilla/5.0 (compatible; RAGSearchBot/1.0;)",
    "scrape_interval": 24 * 60 * 60,  # Default scrape interval in seconds (24 hours)
    "max_depth": 3,  # Default maximum depth for crawling
    "max_pages": 200,  # Default maximum number of pages to scrape
    "concurrency": 25,  # Default number of concurrent requests
}

__default_vector_db_config = {
    # Default vector database configuration
    "host": "localhost",
    "port": 6333,  # Default port for Qdrant
    "collection_name": "default_collection",  # Default collection name
    "vector_size": 384,  # Size for all-MiniLM-L6-v2 embeddings
    "distance_metric": "cosine"  # Distance metric for vector similarity
}

__default_llm_config = {
    # Default LLM configuration
    "model_name": "gemma3:12b",  # Default model name
    "disable": False
}


SCRAPE_CONFIGURATION = "SCRAPE_CONFIGURATION"
VECTOR_DB_CONFIGURATION = "VECTOR_DB_CONFIGURATION"
LLM_CONFIGURATION = "LLM_CONFIGURATION"


def initialize():
    """
    Load default configuration and initalize logging
    This function should be called at the start of the application
    to ensure that the configuration is set up and logging is ready.
    """
    # Load environment variables
    load_dotenv()

    # Setup logging
    log_level = get_log_level()
    logging.basicConfig(    
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()  # Log to console
        ]
    )

    # Setup crawling configuration
    __default__config[SCRAPE_CONFIGURATION] = json.loads(os.getenv(SCRAPE_CONFIGURATION, __default_scrape_config))

    # Setup vector database configuration
    __default__config[VECTOR_DB_CONFIGURATION] = json.loads(os.getenv(VECTOR_DB_CONFIGURATION, __default_vector_db_config))

    # Setup LLM configuration
    __default__config[LLM_CONFIGURATION] = json.loads(os.getenv(LLM_CONFIGURATION, __default_llm_config))

    logging.info(f"Configuration {__default__config} initialized successfully.")


def get_log_level():
    """
    Get the logging level from environment variable or default to INFO
    Returns:
        int: Logging level constant from logging module
    """
    log_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
    if log_level == "DEBUG":
        return logging.DEBUG,
    elif log_level == "WARNING":
        return logging.WARNING,
    elif log_level == "ERROR":
        return logging.ERROR,
    return logging.INFO


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name
    Args:
        name (str): Name of the logger
    Returns:
        logging.Logger: Logger instance
    """
    if not name:
        raise ValueError("Logger name cannot be empty")
    
    return logging.getLogger(name)


def get_config() -> dict:
    """
    Get the default configuration settings
    Returns:
        dict: A copy of the default configuration dictionary
    """
    return __default__config.copy()


def update_config(new_config: dict):
    """
    Update the default configuration with new settings
    Args:
        new_config (dict): Dictionary containing new configuration settings
    """
    __default__config.update(new_config)
    logging.info(f"Configuration updated: {__default__config}")


def get_scraper_useragent() -> str:
    """
    Get the user agent string for web scraping
    Returns:
        str: User agent string
    """
    print(f"config is {get_config()}")
    scraper_config = get_config()[SCRAPE_CONFIGURATION] if hasattr(get_config(), SCRAPE_CONFIGURATION) else {}
    if "user_agent" in scraper_config:
        return scraper_config["user_agent"]
    
    # Fallback to environment variable or default user agent
    return "Mozilla/5.0 (compatible; RAGChatBot/1.0;)"


def is_llm_disabled() -> bool:
    """
    Check if the LLM is disabled in the configuration
    Returns:
        bool: True if LLM is disabled, False otherwise
    """
    llm_config = get_config()[LLM_CONFIGURATION]
    return llm_config.get("disable", False)
