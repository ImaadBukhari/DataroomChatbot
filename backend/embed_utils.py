import os
import json
import numpy as np
import faiss
from typing import List, Dict, Any, Tuple
import tiktoken
from openai import OpenAI
import logging

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

class EmbeddingManager:
    def __init__(self, chunk_size: int = 300):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.chunk_size = chunk_size
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.index_path = "faiss_index/index.faiss"
        self.metadata_path = "faiss_index/metadata.json"
        self.dimension = 1536  # OpenAI ada-002 embedding dimension
        
        # Ensure faiss_index directory exists
        os.makedirs("faiss_index", exist_ok=True)
    
    async def process_and_embed_files(self, files: List[Dict[str, Any]]):
        """Process files into chunks and create embeddings"""
        try:
            all_chunks = []
            all_metadata = []
            
            for file in files:
                chunks = self._split_into_chunks(file['content'])
                for i, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    all_metadata.append({
                        'file_id': file['id'],
                        'file_name': file['name'],
                        'chunk_index': i,
                        'chunk_text': chunk,  # Store the actual chunk text
                        'mime_type': file['mime_type'],
                        'modified_time': file.get('modified_time')
                    })
            
            if not all_chunks:
                logger.warning("No chunks to embed")
                return
            
            logger.info(f"Creating embeddings for {len(all_chunks)} chunks")
            
            # Create embeddings
            embeddings = await self._create_embeddings(all_chunks)
            
            # Create and save FAISS index
            self._create_and_save_index(embeddings, all_metadata)
            
            logger.info("Successfully created and saved embeddings")
            
        except Exception as e:
            logger.error(f"Error processing and embedding files: {str(e)}")
            raise
    
    def _split_into_chunks(self, text: str) -> List[str]:
        """Split text into chunks of specified token size"""
        if not text.strip():
            return []
        
        tokens = self.encoding.encode(text)
        chunks = []
        
        for i in range(0, len(tokens), self.chunk_size):
            chunk_tokens = tokens[i:i + self.chunk_size]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
        
        return chunks
    
    async def _create_embeddings(self, texts: List[str]) -> np.ndarray:
        """Create embeddings for a list of texts"""
        embeddings = []
        batch_size = 100  # Process in batches to avoid rate limits
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self.client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=batch
                )
                
                batch_embeddings = [data.embedding for data in response.data]
                embeddings.extend(batch_embeddings)
                
                logger.info(f"Created embeddings for batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
                
            except Exception as e:
                logger.error(f"Error creating embeddings for batch {i//batch_size + 1}: {str(e)}")
                raise
        
        return np.array(embeddings, dtype=np.float32)
    
    def _create_and_save_index(self, embeddings: np.ndarray, metadata: List[Dict[str, Any]]):
        """Create FAISS index and save with metadata"""
        try:
            # Create FAISS index
            index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
            
            # Normalize embeddings for cosine similarity
            faiss.normalize_L2(embeddings)
            
            # Add embeddings to index
            index.add(embeddings)
            
            # Save index
            faiss.write_index(index, self.index_path)
            
            # Save metadata
            with open(self.metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Saved FAISS index with {index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Error creating and saving index: {str(e)}")
            raise
    
    def load_index(self) -> Tuple[faiss.Index, List[Dict[str, Any]]]:
        """Load FAISS index and metadata"""
        try:
            if not self.index_exists():
                raise ValueError("Index does not exist")
            
            index = faiss.read_index(self.index_path)
            
            with open(self.metadata_path, 'r') as f:
                metadata = json.load(f)
            
            return index, metadata
            
        except Exception as e:
            logger.error(f"Error loading index: {str(e)}")
            raise
    
    def index_exists(self) -> bool:
        """Check if FAISS index exists"""
        return os.path.exists(self.index_path) and os.path.exists(self.metadata_path)
    
    def get_indexed_file_count(self) -> int:
        """Get count of indexed files"""
        try:
            if not self.index_exists():
                return 0
            
            with open(self.metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Count unique files
            unique_files = set(item['file_id'] for item in metadata)
            return len(unique_files)
            
        except Exception as e:
            logger.error(f"Error getting file count: {str(e)}")
            return 0
    
    async def embed_query(self, query: str) -> np.ndarray:
        """Create embedding for a query"""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-ada-002",
                input=[query]
            )
            
            embedding = np.array([response.data[0].embedding], dtype=np.float32)
            faiss.normalize_L2(embedding)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error embedding query: {str(e)}")
            raise