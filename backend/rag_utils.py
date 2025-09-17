import numpy as np
from typing import List, Tuple, Dict, Any
from openai import OpenAI
import logging

from config import OPENAI_API_KEY
from embed_utils import EmbeddingManager

logger = logging.getLogger(__name__)

class RAGManager:
    def __init__(self, embedding_manager: EmbeddingManager):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.embedding_manager = embedding_manager
        self.index = None
        self.metadata = None
        self.load_index()
    
    def load_index(self):
        """Load the FAISS index and metadata"""
        try:
            if self.embedding_manager.index_exists():
                self.index, self.metadata = self.embedding_manager.load_index()
                logger.info(f"Loaded index with {len(self.metadata)} chunks")
            else:
                logger.warning("No index found - please update embeddings first")
                self.index = None
                self.metadata = None
        except Exception as e:
            logger.error(f"Error loading index: {str(e)}")
            self.index = None
            self.metadata = None
    
    async def answer_question(self, question: str, top_k: int = 5) -> Tuple[str, List[str]]:
        """Answer a question using RAG"""
        try:
            if self.index is None:
                return "I don't have access to any documents yet. Please update the dataroom first.", []
            
            # Get relevant context
            relevant_chunks, sources = await self._get_relevant_context(question, top_k)
            
            if not relevant_chunks:
                return "I couldn't find any relevant information in the dataroom to answer your question.", []
            
            # Generate answer using GPT
            answer = await self._generate_answer(question, relevant_chunks)
            
            return answer, sources
            
        except Exception as e:
            logger.error(f"Error answering question: {str(e)}")
            return f"Sorry, I encountered an error while processing your question: {str(e)}", []
    
    async def _get_relevant_context(self, query: str, top_k: int) -> Tuple[List[str], List[str]]:
        """Get relevant context chunks for a query"""
        try:
            # Embed the query
            query_embedding = await self.embedding_manager.embed_query(query)
            
            # Search the index
            scores, indices = self.index.search(query_embedding, top_k)
            
            relevant_chunks = []
            sources = []
            seen_files = set()
            
            for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                # Lower the similarity threshold
                if score > 0.5:  # Reduced from 0.7 to 0.5
                    chunk_metadata = self.metadata[idx]
                    
                    # Use the actual chunk text
                    chunk_text = chunk_metadata.get('chunk_text', '')
                    if chunk_text:
                        relevant_chunks.append(chunk_text)
                    
                    # Add source if not already added
                    file_name = chunk_metadata['file_name']
                    if file_name not in seen_files:
                        sources.append(file_name)
                        seen_files.add(file_name)
            
            logger.info(f"Found {len(relevant_chunks)} relevant chunks from {len(sources)} sources")
            return relevant_chunks, sources
            
        except Exception as e:
            logger.error(f"Error getting relevant context: {str(e)}")
            return [], []
    
    async def _generate_answer(self, question: str, context_chunks: List[str]) -> str:
        """Generate an answer using GPT with context"""
        try:
            context = "\n\n".join(context_chunks)
            
            prompt = f"""You are a helpful assistant that answers questions about documents in a dataroom. 
Use the provided context to answer the question. If the context doesn't contain enough information to answer the question, say so clearly.

Context from dataroom documents:
{context}

Question: {question}

Answer:"""

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions about dataroom documents. Be concise and accurate."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return f"Sorry, I encountered an error while generating the answer: {str(e)}"