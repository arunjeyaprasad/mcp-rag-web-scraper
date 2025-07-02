from fastapi import FastAPI, BackgroundTasks, Response, status
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Union
import asyncio
import time
import threading
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import config
from storage import DocumentStore
from urllib.parse import urlparse
from langchain_ollama import OllamaLLM


# Global constants
scrapers = {}
llm = None
logger = config.get_logger(__name__)


# Pydantic models
class ScrapeRequest(BaseModel):
    url: str
    schedule_interval_hours: Optional[int] = None

class ScrapeResponse(BaseModel):
    status: str

class SearchRequest(BaseModel):
    domain: str
    query: str

class ErrorResponse(BaseModel):
    error: str
    code: Optional[int] = None


# Initialize scheduler
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to start and stop the scheduler"""
    logger.info("Starting application...")
    try:
        scheduler.start()
        logger.info("Scheduler started successfully")
        yield
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        logger.info("Shutting down application...")
        scheduler.shutdown()
        logger.info("Scheduler stopped")


app = FastAPI(title="RAG Supported Scraper API", version="1.0.0", lifespan=lifespan)

def check_domain(url: Optional[str]) -> Optional[str]:
    """
        Validate the domain name from the incoming request
        Args:
            request: The http request
        Returns:
            str: The domain as is if present and None otherwise
    """
    if url is None:
        return url
    if url.startswith("http"):
        return url
    logger.error(f"Invalid domain received {url}")


def extract_domain(domain: str) -> str:
    """
        Extract the domain name from the http url.
        i.e., https://some.abcd.com will be parsed and returns
        some.abcd.com
        Args:
            domain: http domain from the http request
        Returns:
            str: The parsed host alone from the url
    """
    if not domain:
        return None
    parsed_uri = urlparse(domain)
    return parsed_uri.hostname


@app.post("/scrape/start", response_model=Union[ScrapeResponse, ErrorResponse])
async def start_scrape(request: ScrapeRequest, response: Response, background_tasks: BackgroundTasks):
    """
    Start scraping the specified website URL.
    Args:
        request (ScrapeRequest): The request containing the URL and optional schedule interval.
        background_tasks (BackgroundTasks): Background tasks to run after the response is sent.
    Returns:
        ScrapeResponse: The response indicating the status of the scraping operation.
    """

    # Lazy initialisation to let config get initialised
    from scrapers import WebsiteScraper

    domain = check_domain(request.url)
    if domain is None:
        # Bad Request. No search query provided
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Missing domain in the request. Specify using 'url' field",
            code=status.HTTP_400_BAD_REQUEST
        )

    host = extract_domain(domain)
    if hasattr(scrapers, host):
        # Scraper already present
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error=f"Scraper for domain {host} already exists",
            code=status.HTTP_400_BAD_REQUEST
        )
    
    scraper = WebsiteScraper(domain, collection_name=host, override_robots=True)
    background_tasks.add_task(scraper.scrape_website)
    # If schedule interval is provided, start the scraper with a schedule
    if request.schedule_interval_hours:
        interval = request.schedule_interval_hours
        logger.info(f"Scheduling scraper for {host} every {interval} hours")
        scheduler.add_job(
            scraper.scrape_website,
            IntervalTrigger(hours=interval),
            id=f"scraper_{host}",
            replace_existing=True
        )

    scrapers[host] = scraper
    logger.info("Web scraping started")
    return ScrapeResponse(status="Scraping started successfully")


@app.put("/scrape/stop", response_model=Union[ScrapeResponse, ErrorResponse])
def stop_scrape(request: ScrapeRequest, response: Response):
    domain = check_domain(request.url)
    if domain is None:
        # Bad Request. No search query provided
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Missing domain in the request. Specify using 'url' field",
            code=status.HTTP_400_BAD_REQUEST
        )
    
    domain = extract_domain(domain)
    scraper = scrapers.get(domain, None)
    if scraper is None:
        # Bad Request. No scraper present for the domain
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="No scraper present with this domain",
            code=status.HTTP_400_BAD_REQUEST
        )
    scraper.stop()
    # Remove the scraper from the dictionary
    del scrapers[domain]
    # Remove the job from the scheduler if it exists
    job_id = f"scraper_{domain}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    logger.info(f"Scraper for {domain} stopped successfully")
    # Return a success response
    response.status_code = status.HTTP_200_OK
    return ScrapeResponse(
        status=f"Scraper for {domain} stopped successfully"
    )


@app.get("/statusz", response_model=Union[ScrapeResponse, ErrorResponse])
def statusz(response: Response):
    running = True
    errors = []
    # Check if Vector database is up and running ?
    statusz = _check_datastore()
    if statusz is False:
        errors.append("Local Vector DB is offline")
        running = False
    # Check if Ollama is running
    if not config.is_llm_disabled():
        statusz, _ = check_ollama_status()
        if statusz is False:
            errors.append("Local LLM is offline")
            running = False
    if not running:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ErrorResponse(
            error=f"Some services are offline {errors}",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    # Everything is running fine
    response.status_code = status.HTTP_200_OK
    return ScrapeResponse(
        status="All systems online",
        code=status.HTTP_200_OK
    )

@app.get("/scrape/status", response_model=Dict[str, Any])
def scrape_status(response: Response):
    """
        Get the status of all active scrapers.
        Returns:
            Dict[str, Any]: A dictionary containing the status of each scraper.
    """
    scraper_status = {}
    for domain, scraper in scrapers.items():
        scraper_status[domain] = {
            "progress": scraper.progress()
        }
    
    response.status_code = status.HTTP_200_OK
    response.value = scraper_status
    
    return scraper_status

@app.get("/search", response_model=Union[ErrorResponse, Dict[str, Any]])
def search(request: SearchRequest, response: Response):
    domain = request.domain
    
    if domain is None:
        # Bad Request. No search query provided
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Missing domain in the request. Specify using 'url' field",
            code=status.HTTP_400_BAD_REQUEST
        )

    query = request.query
    if query is None:
        # Bad Request. No search query provided
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Missing search query in the request. Specify using 'query' field",
            code=status.HTTP_400_BAD_REQUEST
        )
    logger.info(f"Search query received for domain {domain} with query: {query}")

    domain = extract_domain(domain)
    client = DocumentStore(domain)
    docs = client.search_documents(query)

    if config.is_llm_disabled():
        # If LLM is disabled, return the raw search results
        if not docs:
            response.status_code = status.HTTP_404_NOT_FOUND
            return ErrorResponse(
                error="No context info found from the knowledge base",
                code=status.HTTP_404_NOT_FOUND
            )
        # Return the results as a JSON response
        response.status_code = status.HTTP_200_OK
        return {
            "results": docs
        }
    
    # Extract and format the results
    results = "\n".join([doc.get("text", "") for doc in docs])
    
    augmented_query = f"Context: {results}\n\nQuestion: {query}\nAnswer:"
    resp = query_ollama(augmented_query)
    if not resp:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ErrorResponse(
            error="Failed to get response from LLM",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    # Return the response from the LLM
    response.status_code = status.HTTP_200_OK
    return {
        "query": query,
        "response": resp
    }


# Function to interact with the Ollama LLM
def query_ollama(prompt):
    """
    Send a query to Ollama and retrieve the response.
    
    Args:
        prompt (str): The input prompt for Ollama.
    
    Returns:
        str: The response from Ollama.
    """
    if not llm:
        raise ValueError("LLM is not initialized / disabled. Please check your configuration.")
    
    return llm.invoke(prompt)

def check_ollama_status():
    """
        Check if Ollama is running

        Returns:
            bool: True if running and false otherwise
            str: Simple error message
    """
    try:
        # Check if the API is responding
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return True, data
        else:
            return False, f"HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Connection refused - Ollama not running"
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except Exception as e:
        return False, f"Error: {e}"


def _check_datastore():
    """
        Check if the local vector database (Qdrant) is running
    Returns:
        bool: True if running and false otherwise
    """
    try:
        vector_db_config = config.get_config().get(config.VECTOR_DB_CONFIGURATION)
        if not vector_db_config:
            return False
        # Check if the Qdrant server is running
        host = vector_db_config.get("host")
        port = vector_db_config.get("port")
        if not host or not port:
            logger.error("Vector DB host or port not configured")
            return False
        # Make a simple request to the health endpoint of Qdrant
        url = f"http://{host}:{port}/healthz"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return True
        return False
    except Exception as e:
        return False


def _monitor_scraper_progress():
    """
        Monitor the progress of the web scrapers and log their status
    """
    while True:
        for domain, scraper in scrapers.items():
            logger.info(f"Progress for scraper {domain}: {scraper.progress()}")

        # Sleep for a while before checking again
        try:
            time.sleep(30)  # Check every 60 seconds
        except (KeyboardInterrupt, SystemExit):
            logger.info("Stopping scraper progress monitoring")


# This is the main entry point for the RAG Search application
if __name__ == '__main__':
    # Load config
    config.initialize()

    # Start a progess monitoring thread
    progress_thread = threading.Thread(target=_monitor_scraper_progress)
    progress_thread.daemon = True
    progress_thread.start()
    
    # Initialize the LLM
    if not config.is_llm_disabled():
        llm = OllamaLLM(model=config.get_config().get("llm_model", "gemma3:12b"))

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.get_config().get("server_port", 8090))