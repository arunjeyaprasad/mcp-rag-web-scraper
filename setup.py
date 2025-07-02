from setuptools import setup, find_packages

setup(
    name="mcp-rag-web-scraper",
    version="1.0.0",
    description="A web scraper for RAG (Retrieval-Augmented Generation) using MCP",
    author="A J Arun Jeya Prasad",
    packages=find_packages(),
    install_requires=[
        "playwright>=1.42.0",
        "python-dotenv>=1.1.0",
        "apscheduler>=3.10.1",
        "langchain==0.3.25",
        "langchain-huggingface==0.3.0",
        "qdrant-client==1.8.0",
        "sentence-transformers==2.5.1",
        "pytest-asyncio>=0.21.0",
        "fastmcp>=2.8.1",
        "fastapi>=0.115.14",
        "langchain_ollama>=0.3.3"
    ],
)