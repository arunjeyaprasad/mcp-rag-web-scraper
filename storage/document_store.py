from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import SearchParams
from config import config
from typing import List, Dict
import logging


class DocumentStore:
    def __init__(self, collection_name: str = "default_collection"):
        self.collection_name = collection_name
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

        self.vector_config = config.get_config().get(config.VECTOR_DB_CONFIGURATION)
        # Initialize Qdrant client
        self.client = QdrantClient(
            host=self.vector_config.get("host", "localhost"),
            port=self.vector_config.get("port", 6333)
        )

        # Setup logging
        self.logger = logging.getLogger(__name__)

        # Ensure collection exists
        self._create_collection_if_not_exists()

    def _create_collection_if_not_exists(self):
        """
            Create Qdrant collection if it doesn't exist
        """
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_config.get("vector_size", 384),  # all-MiniLM-L6-v2 embedding size
                    distance=models.Distance.COSINE
                )
            )
        self.logger.info(f"Created collection: {self.collection_name}")

    def store_documents(self, documents: List[Dict]):
        """
            Process and store documents in Vector Database (Qdrant)
            Args:
                documents (List[Dict]): List of documents to be stored, each document should have:
                - content (str): The text content of the document
                - url (str): URL of the document
                - title (str): Title of the document
                - metadata (Dict): Additional metadata for the document
        """
        for doc in documents:
            try:
                # Create LangChain document
                langchain_doc = Document(
                    page_content=doc["content"],
                    metadata={
                        "url": doc["url"],
                        "title": doc["title"],
                        "content_hash": doc.get("content_hash", ""),
                        "last_modified": doc.get("last_modified", None),
                        **doc.get("metadata", {})
                    }
                )

                # Split document into chunks
                doc_chunks = self.text_splitter.split_documents([langchain_doc])

                # Create embeddings and store in Qdrant
                for chunk in doc_chunks:
                    embedding = self.embeddings.embed_query(chunk.page_content)
                    self.client.upsert(
                        collection_name=self.collection_name,
                        points=models.Batch(
                            ids=[abs(hash(chunk.page_content))],
                            vectors=[embedding],
                            payloads=[{
                                "text": chunk.page_content,
                                "metadata": chunk.metadata
                            }]
                        )
                    )
                self.logger.debug(f"Stored document: {doc['url']}")
            except Exception as e:
                self.logger.error(f"Error storing document: {str(e)} {doc.get('url', 'unknown')}")

    def search_documents(self, query: str, top_k: int = 5, similarity_threshold: float = None) -> List[Dict[str, any]]:
        """
            Search for documents in the vector database
            Args:
                query (str): The search query
                top_k (int): Number of top results to return
                similarity_threshold (float):
                    Minimum similarity score to filter results
        """
        if not query:
            self.logger.warning("Empty query provided for search.")
            return []
        if top_k <= 0:
            self.logger.warning("Invalid top_k value provided for search, \
                                defaulting to 5.")
            top_k = 5
        try:
            embedding = self.embeddings.embed_query(query)
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=embedding,
                limit=top_k,
                search_params=SearchParams(
                    hnsw_ef=128  # Use default HNSW algorithm
                ),
                score_threshold=similarity_threshold if similarity_threshold else 0.0
            )

            return [
                {
                    "text": result.payload["text"],
                    "metadata": result.payload["metadata"],
                    "score": result.score
                } for result in results
            ]

        except Exception as e:
            self.logger.error(f"Error searching documents: {str(e)}")
            return []

    def close(self):
        """Close the Qdrant client connection"""
        try:
            self.client.close()
            self.logger.info("Closed Qdrant client connection.")
        except Exception as e:
            self.logger.error(f"Error closing Qdrant client: {str(e)}")
