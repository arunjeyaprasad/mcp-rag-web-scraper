# mcp-rag-web-scraper

Customizable web scraper that can be used to build a knowledge base which can be integrated with a RAG system for Search. Supports MCP integration as well for querying

# Overview

This repo contains two indepdendent applications
1) Web Scraper that scrapes a website and stores the information in a local vector database to create an offline knowledge base which can be searched using Natural language queries.
2) MCP Server that can be configured with apps like Claude Desktop app which can then interface with the Scraper service
