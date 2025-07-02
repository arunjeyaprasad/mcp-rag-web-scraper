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
<li>Docker (<u>Optional</u> If you want to run as a container</li>

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

You can use conda to create the environment and manage the dependencies
```
conda create -n rag-search-service python=3.11
conda activate rag-search-service
pip install -r requirements.txt
```

<u>Note</u>: Untested on Windows as I don't have access to one. Please update the README with a section for Windows

# License
This project is licensed under the MIT [License](LICENSE)

