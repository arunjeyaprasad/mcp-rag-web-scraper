#!/usr/bin/env python3
"""
MCP Server for our RAG Scraper

A Model Context Protocol server built with FastMCP that provides tools for 
invoking remote HTTP services. 
This server can be integrated with Claude Desktop or other MCP-compatible clients.
This server is designed to work with a remote scraping service, allowing users
to perform search operations, start and stop scraping tasks, and test the
connection to the service.
"""
import os
import json
import httpx
import logging

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("MCP Server for RAG Search", version="1.0.0")

# Configuration for allowed hosts (security measure)
ALLOWED_HOSTS = [

]

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_REMOTE_RAG_SERVICE = "http://localhost:8090"

# Get the remote RAG service URL from environment variable or use default
SERVICE_URL = os.getenv("RAG_SERVICE_URL", DEFAULT_REMOTE_RAG_SERVICE)

# Pydantic Models
class SearchRequest(BaseModel):
    """
        Model for search request parameters.
    """
    domain: str = Field(
        ...,
        description="The domain to search within, e.g., 'example.com'"
    )
    query: str = Field(
        ...,
        description="The search query to execute"
    )


class ScrapeRequest(BaseModel):
    """
        Model for scrape request parameters.
    """
    url: str = Field(
        ...,
        description="The URL to scrape"
    )
    schedule_interval_hours: Optional[int] = Field(
        24,
        description="The interval in hours to reschedule the scrape (default: 24 hours)"
    )


class ErrorResponse(BaseModel):
    """
        Model for error responses.
    """
    error: str = Field(
        ...,
        description="Error message describing what went wrong"
    )
    code: Optional[int] = Field(
        None,
        description="Optional error code for more specific error identification"
    )


class SuccessResponse(BaseModel):
    """
        Model for successful responses.
    """
    status: str = Field(
        ...,
        description="Success message indicating the operation was successful"
    )


# Utility Functions
def is_url_allowed(url: str) -> bool:
    """
        Check if the URL is from an allowed host.
        Args:
            url: The URL to check
        Returns:
            bool: True if the URL's host is in the allowed list,
                  False otherwise
    """
    try:
        parsed = urlparse(url)
        # If ALLOWED_HOSTS is empty, allow all hosts
        if not ALLOWED_HOSTS or len(ALLOWED_HOSTS) == 0:
            return True
        return parsed.hostname in ALLOWED_HOSTS
    except Exception:
        return False


def format_response(response: httpx.Response) -> Dict[str, Any]:
    """Format HTTP response for MCP tool result."""
    try:
        # Try to parse JSON response
        json_data = response.json()
    except Exception:
        json_data = None

    return {
        "status_code": response.status_code,
        "json": json_data,
        "text": response.text[:2000] if len(response.text) > 2000 else response.text,
        "elapsed_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else None,
        "success": 200 <= response.status_code < 300
    }

# MCP Tools
@mcp.tool()
async def search(
    url: str,
    query: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> str:
    """
    Make a GET request to a remote HTTP service.

    Args:
        url: The URL to make the GET request to
        query: The search query to include in the request
        timeout: Request timeout in seconds (default: 30)

    Returns:
        JSON string containing the response data
    """
    if not is_url_allowed(url):
        return json.dumps({
            "error": f"URL not allowed. Host must be in: {', '.join(ALLOWED_HOSTS)}"
        })

    # Prepare parameters for the GET request
    payload = SearchRequest(
        domain=urlparse(url).netloc,
        query=query
    )

    url = f"{SERVICE_URL}/search"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                json=payload.model_dump(),
                timeout=timeout
            )

            result = format_response(response)
            return json.dumps(result, indent=2)

    except httpx.TimeoutException:
        return json.dumps({"error": "Request timed out"})
    except Exception as e:
        logger.error(f"GET request error: {str(e)}")
        return json.dumps({"error": str(e)})


@mcp.tool()
async def start_scrape(
    url: str,
    schedule_interval_hours: Optional[int] = 24,
    timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> str:
    """
    Start the scraping of the given website URL.

    Args:
        url: The URL to scrape
        schedule_interval_hours: Interval in hours to reschedule the scrape (default: 24 hours)
        timeout: Request timeout in seconds (default: 30)

    Returns:
        JSON string containing the response data
    """
    if not is_url_allowed(url):
        return json.dumps({
            "error": f"URL not allowed. Host must be in: {', '.join(ALLOWED_HOSTS)}"
        })

    headers = {}
    path = f"{SERVICE_URL}/scrape/start"
    payload = ScrapeRequest(url=url, schedule_interval_hours=schedule_interval_hours)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                path,
                headers=headers,
                json=payload.model_dump(),
                timeout=timeout
            )

            result = format_response(response)
            return json.dumps(result, indent=2)

    except httpx.TimeoutException:
        return json.dumps({"error": "Request timed out"})
    except Exception as e:
        logger.error(f"POST request error: {str(e)}")
        return json.dumps({"error": str(e)})


@mcp.tool()
async def stop_scrape(
    url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> str:
    """
    Stop the scraping of the given website URL.

    Args:
        url: The URL which was provided to scrape via start_scrape
        timeout: Request timeout in seconds (default: 30)

    Returns:
        JSON string containing the response data
    """
    if not is_url_allowed(url):
        return json.dumps({
            "error": f"URL not allowed. Host must be in: {', '.join(ALLOWED_HOSTS)}"
        })

    headers = {}
    path = f"{SERVICE_URL}/scrape/stop"
    payload = ScrapeRequest(url=url)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                path,
                headers=headers,
                json=payload.model_dump(),
                timeout=timeout
            )

            result = format_response(response)
            return json.dumps(result, indent=2)

    except httpx.TimeoutException:
        return json.dumps({"error": "Request timed out"})
    except Exception as e:
        logger.error(f"POST request error: {str(e)}")
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_scrape_status() -> str:
    """
    Get the status of the scraping service.

    Args:
        None

    Returns:
        JSON string containing the scrape status
    """
    url = f"{SERVICE_URL}/scrape/status"
    if not is_url_allowed(url):
        return json.dumps({
            "error": f"URL not allowed. Host must be in: {', '.join(ALLOWED_HOSTS)}"
        })

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)

            result = format_response(response)
            return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e)
        })


@mcp.tool()
async def test_connection() -> str:
    """
    Test connection to the service with a simple GET request.
    Args:
        None
    Returns:
        JSON string containing the test results
    """
    url = f"{SERVICE_URL}/statusz"
    if not is_url_allowed(url):
        return json.dumps({
            "error": f"URL not allowed. Host must be in: {', '.join(ALLOWED_HOSTS)}"
        })

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)

            result = {
                "test_passed": 200 <= response.status_code < 300,
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else None,
                "url": str(response.url)
            }
            return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "test_passed": False,
            "error": str(e)
        })

if __name__ == "__main__":
    logger.info("Starting MCP Server for RAG Search")
    mcp.run()
