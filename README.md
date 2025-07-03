[![Python application](https://github.com/arunjeyaprasad/mcp-rag-web-scraper/actions/workflows/python-app.yml/badge.svg)](https://github.com/arunjeyaprasad/mcp-rag-web-scraper/actions/workflows/python-app.yml)
# mcp-rag-web-scraper

Customizable web scraper that can be used to build a knowledge base which can be integrated with a RAG system for Search. Supports MCP integration as well for querying

# Overview

This repo contains two indepdendent applications
1) Web Scraper that scrapes a website and stores the information in a local vector database to create an offline knowledge base which can be searched using Natural language queries.
2) [MCP Server](mcp) that can be configured with apps like Claude Desktop app which can then interface with the Scraper service

# Key Features
<ul>
<li><b>Customizable Scrape parameters</b>: Refer to [env](.env) file for detailed parameters</li>
<li><b>Scheduled Scraping</b>: You can scrape for new content from the target website at the preferred scheduling interval</li>
<li><b>Override robots.txt</b>: Be sensitive to the websites :) Their job is to be always available to viewers not to serve bots. An ability to override the robots file is provided but still with crawl delay and max pages to not hurt the sentiments of the website</li>
<li><b>RESTful API</b>: APIs to initiate/stop scraping, progress monitoring and health monitoring</li>
<li><b>Integration ready</b>: Available for integration with AI Agents or MCP clients like Claude Desktop App</li>
</ul>

# Quick Start
## Prerequisites
<ul>
<li>Python 3.11 or greater</li>
<li>Docker (<u>Optional</u> If you want to run as a container)</li>
</ul>

## Running via docker
```
docker-compose up
```
<p>This will create a docker image of the python app and also installs the latest qdrant vector database.</p>

## Running directly from Mac

Edit the /etc/hosts file to include
```
127.0.0.1       host.docker.internal
```
<u>Note:</u> You can run a qdrant database in a different host if needed. Be sure to adjust the hostname of the qdrant client as required in [.env](.env) file.

First, start the qdrant service / container
```
docker pull qdrant/qdrant
docker run -p 6333:6333 -p 6334:6334 \
    -v "$(pwd)/qdrant_storage:/qdrant/storage:z" \
    qdrant/qdrant
```

To start the app, you may use conda to create the environment and manage the dependencies
```
conda create -n rag-search-service python=3.11
conda activate rag-search-service
pip install -r requirements.txt
python app.py
```

<u>Note</u>: Untested on Windows as I don't have access to one. Please update the README with a section for Windows

# REST APIs
## Health Check
```http
GET http://localhost:8090/statusz
```

Response Body:
```json
{
    "status": "All systems online"
}
```

## Start Scraping
```http
POST http://localhost:8090/scrape/start
```

Request Body:
```json
{
    "url": "https://www.google.com",
    "schedule_interval_hours": 12
}
```
`schedule_interval_hours` is an optional field. It indicates the service to scrape the website for every 12 hours once.

Response Body:
```json
{
    "status": "Scraping started successfully"
}
```

## Stop Scraping
```http
PUT http://localhost:8090/scrape/stop
```

Request Body:
```json
{
    "url": "https://www.google.com"
}
```
This stops any scheduled scraping or ongoing scraping activities for the given domain

## Search
```http
POST http://localhost:8090/search
```

Request Body:
```json
{
    "domain": "url used in the start scrape request",
    "query": "Find me the best catalogue from the collection"
}
```

# Integration with Claude Desktop

Copy past this MCP Server configuration to `/$HOME/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "RAGSearchService": {
      "cwd": "mcp-rag-web-scraper/mcp",
      "command": "/bin/bash",
      "args": [
        "-c",
        "cd mcp-rag-web-scraper/mcp && pip install -r requirements.txt && python app.py"
      ],
      "env": {
        "PYTHONPATH": "mcp-rag-web-scraper/mcp",
        "RAG_SERVICE_URL": "http://localhost:8090",
        "PATH": "/opt/miniconda3/envs/rag/bin/:$PATH"
      }
    }
  }
}
```
<u>Note:</u> Adjust the `cwd`, `args` and `PATH` appropriately based on where the code is cloned in your machine and the python version you intend to use

# Snapshots
Now your Claude desktop shows your service and is ready to hit our RAG Search service
<div>
<img src="assets/Claude1 - Service.png" alt="Service" width="46%">
<img src="assets/Claude2 - APIs.png" alt="APIs" width="45%">
</div>

# Integration with Ollama
You may also choose to skip the mcp route and interface the system directly with a local LLM (Example: Ollama) in your local machine.
To accomplish this set `disable` to `false` in [.env](.env) file and start the app
In this approach the search response from qdrant db is forwarded as additional context along with the actual search query and the final response from ollama is returned back to the user.

## To run ollama locally
Refer to instructions from https://ollama.com on how to set up ollama locally and run your favourite model within ollama. Be sure to update the model name in the [.env](.env) file under `LLM_CONFIGURATION`

# Vector Database Dashboard
You may view the contents of the scraped website in the vector database by launching the dashboard of the qdrant db from http://localhost:6333/dashboard#/collections

# License
This project is licensed under the MIT [License](LICENSE)

