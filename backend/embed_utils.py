import os
import json
import numpy as np
import faiss
import tiktoken
import logging
from typing import List, Dict, Any, Tuple
from openai import OpenAI
from google.cloud import storage
import tempfile



logger = logging.getLogger(__name__)

class EmbeddingManager:
    def __init__(self, chunk_size: int = 300):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.chunk_size = chunk_size
        self.dimension = 1536  # text-embedding-ada-002 dimension
        self.encoding = tiktoken.get_encoding("cl100k_base")
        
        # Cloud Storage configuration
        self.bucket_name = "dataroom-chatbot-storage-dataroom-chatbot-475100"  
        self.index_blob_name = "faiss_index/index.faiss"
        self.metadata_blob_name = "faiss_index/metadata.json"
        
        # Local paths for temporary storage
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "index.faiss")
        self.metadata_path = os.path.join(self.temp_dir, "metadata.json")
        
        # Initialize Cloud Storage client
        try:
            self.storage_client = storage.Client()
            self.bucket = self.storage_client.bucket(self.bucket_name)
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Storage: {e}")
            raise

    async def process_and_embed_files(self, files: List[Dict[str, Any]]):
        """Process files into chunks and create embeddings"""
        try:
            all_chunks = []
            all_metadata = []
            
            for file in files:
                chunks = self._split_into_chunks(file['content'])
                for i, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    
                    # Extract contextual metadata from chunk
                    context_info = self._extract_chunk_context(chunk, file['content'], i)
                    
                    all_metadata.append({
                        'file_id': file['id'],
                        'file_name': file['name'],
                        'chunk_index': i,
                        'chunk_text': chunk,
                        'mime_type': file['mime_type'],
                        'modified_time': file.get('modified_time'),
                        'context_level': context_info['level'],
                        'section_heading': context_info['heading'],
                        'key_entities': context_info['entities']
                    })

            logger.info(f"Received {len(files)} files for embedding")
            for f in files[:10]:  # log the first 10
                logger.info(f" - {f['name']} | content length: {len(f['content'])}")

            
            if not all_chunks:
                logger.warning("No chunks to embed")
                return
            
            logger.info(f"Creating embeddings for {len(all_chunks)} chunks")
            
            # Create embeddings
            embeddings = await self._create_embeddings(all_chunks)
            
            # Create and save FAISS index to Cloud Storage
            self._create_and_save_index(embeddings, all_metadata)
            
            logger.info("Successfully created and saved embeddings to Cloud Storage")
            
        except Exception as e:
            logger.error(f"Error processing and embedding files: {str(e)}")
            raise

    def _split_into_chunks(self, text: str) -> List[str]:
        """Split text into chunks with overlap and sentence boundary awareness"""
        if not text.strip():
            return []
        
        tokens = self.encoding.encode(text)
        chunks = []
        overlap_tokens = 50  # 50 token overlap between chunks
        
        i = 0
        while i < len(tokens):
            # Get chunk tokens
            end_idx = min(i + self.chunk_size, len(tokens))
            chunk_tokens = tokens[i:end_idx]
            
            # Try to break at sentence boundary if possible
            if end_idx < len(tokens):
                # Look for sentence endings in the last 20 tokens
                for j in range(len(chunk_tokens) - 1, max(0, len(chunk_tokens) - 20), -1):
                    chunk_text = self.encoding.decode(chunk_tokens[:j+1])
                    if chunk_text.strip().endswith(('.', '!', '?', '\n')):
                        chunk_tokens = chunk_tokens[:j+1]
                        break
            
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            # Move to next chunk with overlap
            if end_idx >= len(tokens):
                break
            i = end_idx - overlap_tokens
        
        return chunks

    def _extract_chunk_context(self, chunk: str, full_content: str, chunk_index: int) -> Dict[str, Any]:
        """Extract contextual metadata from a chunk"""
        try:
            # Simple heuristic-based context extraction
            context_level = "general"
            section_heading = ""
            entities = []
            
            # Determine context level based on content
            chunk_lower = chunk.lower()
            
            # Fund-level indicators
            fund_keywords = ["fund size", "management fee", "carried interest", "investment thesis", 
                           "fund strategy", "total capital", "fund details", "portfolio construction"]
            
            # Company-level indicators  
            company_keywords = ["company", "startup", "portfolio company", "investment in", 
                              "funding round", "series a", "series b", "valuation"]
            
            # Count keyword matches
            fund_matches = sum(1 for keyword in fund_keywords if keyword in chunk_lower)
            company_matches = sum(1 for keyword in company_keywords if keyword in chunk_lower)
            
            if fund_matches > company_matches:
                context_level = "fund-level"
            elif company_matches > fund_matches:
                context_level = "company-level"
            elif "portfolio" in chunk_lower:
                context_level = "portfolio-level"
            
            # Extract section heading (look for lines starting with # or being all caps)
            lines = chunk.split('\n')
            for line in lines[:3]:  # Check first 3 lines
                line = line.strip()
                if line.startswith('#') or (len(line) < 50 and line.isupper()):
                    section_heading = line
                    break
            
            # Extract potential entities (simple heuristic)
            import re
            # Look for capitalized words that might be company names or fund names
            potential_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', chunk)
            entities = [entity for entity in potential_entities if len(entity) > 3 and len(entity) < 30][:5]
            
            return {
                'level': context_level,
                'heading': section_heading,
                'entities': entities
            }
            
        except Exception as e:
            logger.error(f"Error extracting chunk context: {str(e)}")
            return {
                'level': 'general',
                'heading': '',
                'entities': []
            }

    async def _create_embeddings(self, texts: List[str]) -> np.ndarray:
        """Create embeddings for a list of texts"""
        embeddings = []
        batch_size = 100
        
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
        """Create FAISS index and save to Cloud Storage"""
        try:
            # Create FAISS index
            index = faiss.IndexFlatIP(self.dimension)
            faiss.normalize_L2(embeddings)
            index.add(embeddings)
            
            # Save index locally first
            faiss.write_index(index, self.index_path)
            
            # Save metadata locally first
            with open(self.metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Upload to Cloud Storage
            self._upload_to_storage(self.index_path, self.index_blob_name)
            self._upload_to_storage(self.metadata_path, self.metadata_blob_name)
            
            logger.info(f"Saved FAISS index with {index.ntotal} vectors to Cloud Storage")
            
        except Exception as e:
            logger.error(f"Error creating and saving index: {str(e)}")
            raise

    def _upload_to_storage(self, local_path: str, blob_name: str):
        """Upload file to Cloud Storage"""
        try:
            blob = self.bucket.blob(blob_name)
            blob.upload_from_filename(local_path)
            logger.info(f"Uploaded {blob_name} to Cloud Storage")
        except Exception as e:
            logger.error(f"Error uploading {blob_name}: {str(e)}")
            raise

    def _download_from_storage(self, blob_name: str, local_path: str):
        """Download file from Cloud Storage"""
        try:
            blob = self.bucket.blob(blob_name)
            if blob.exists():
                blob.download_to_filename(local_path)
                logger.info(f"Downloaded {blob_name} from Cloud Storage")
                return True
            else:
                logger.warning(f"Blob {blob_name} does not exist in Cloud Storage")
                return False
        except Exception as e:
            logger.error(f"Error downloading {blob_name}: {str(e)}")
            return False

    def load_index(self) -> Tuple[faiss.Index, List[Dict[str, Any]]]:
        """Load FAISS index and metadata from Cloud Storage"""
        try:
            if not self.index_exists():
                raise ValueError("Index does not exist in Cloud Storage")
            
            # Download from Cloud Storage
            self._download_from_storage(self.index_blob_name, self.index_path)
            self._download_from_storage(self.metadata_blob_name, self.metadata_path)
            
            # Load locally
            index = faiss.read_index(self.index_path)
            
            with open(self.metadata_path, 'r') as f:
                metadata = json.load(f)
            
            logger.info(f"Loaded index with {index.ntotal} vectors from Cloud Storage")
            return index, metadata
            
        except Exception as e:
            logger.error(f"Error loading index: {str(e)}")
            raise

    def index_exists(self) -> bool:
        """Check if FAISS index exists in Cloud Storage"""
        try:
            index_blob = self.bucket.blob(self.index_blob_name)
            metadata_blob = self.bucket.blob(self.metadata_blob_name)
            return index_blob.exists() and metadata_blob.exists()
        except Exception as e:
            logger.error(f"Error checking index existence: {str(e)}")
            return False

    def get_indexed_file_count(self) -> int:
        """Get count of indexed files from Cloud Storage"""
        try:
            if not self.index_exists():
                return 0
            
            # Download metadata to get file count
            self._download_from_storage(self.metadata_blob_name, self.metadata_path)
            
            with open(self.metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Count unique files
            unique_files = set(item['file_id'] for item in metadata)
            return len(unique_files)
            
        except Exception as e:
            logger.error(f"Error getting file count: {str(e)}")
            return 0
        
    async def embed_query(self, query: str) -> np.ndarray:
        """Create embedding for a single query"""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-ada-002",
                input=[query]
            )
            
            embedding = np.array([response.data[0].embedding], dtype=np.float32)
            # Normalize for cosine similarity (same as we do for document embeddings)
            faiss.normalize_L2(embedding)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error creating query embedding: {str(e)}")
            raise