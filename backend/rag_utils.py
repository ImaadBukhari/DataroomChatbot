import numpy as np
from typing import List, Tuple, Dict, Any
from openai import OpenAI
import logging
import os

from config import OPENAI_API_KEY
from embed_utils import EmbeddingManager

logger = logging.getLogger(__name__)

class RAGManager:
    def __init__(self, embedding_manager: EmbeddingManager):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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
    
    async def answer_question(self, question: str, conversation_history: List[Dict[str, str]] = None, top_k: int = 5) -> Tuple[str, List[str]]:
        """Answer a question using RAG with optional conversation history"""
        try:
            if self.index is None:
                return "I don't have access to any documents yet. Please update the dataroom first.", []
            
            # Expand query for better retrieval
            expanded_queries = await self._expand_query(question)
            logger.info(f"Original query: {question}")
            logger.info(f"Expanded queries: {expanded_queries}")
            
            # Get relevant context using expanded queries
            relevant_chunks, sources = await self._get_relevant_context(expanded_queries, top_k)
            
            if not relevant_chunks:
                return "I couldn't find any relevant information in the dataroom to answer your question.", []
            
            # Generate answer using GPT with conversation history
            answer = await self._generate_answer(question, relevant_chunks, conversation_history)
            
            return answer, sources
            
        except Exception as e:
            logger.error(f"Error answering question: {str(e)}")
            return f"Sorry, I encountered an error while processing your question: {str(e)}", []
    
    async def _classify_query_intent(self, query: str) -> Dict[str, Any]:
        """Classify query intent to understand what level of information is being asked"""
        try:
            intent_prompt = f"""Analyze this query about a venture capital dataroom and classify its intent.
            
            Query: "{query}"
            
            Determine:
            1. Information level (fund-level, portfolio-level, company-specific, or general)
            2. Key entities mentioned (fund names, company names, metrics)
            3. Intent keywords to help filter relevant chunks
            
            Respond in JSON format:
            {{
                "level": "fund-level|portfolio-level|company-specific|general",
                "entities": ["entity1", "entity2"],
                "keywords": ["keyword1", "keyword2"],
                "exclude_keywords": ["exclude1", "exclude2"]
            }}
            
            Examples:
            - "What is the fund size?" → level: "fund-level", keywords: ["fund", "size", "total", "capital"]
            - "Tell me about TechCorp" → level: "company-specific", entities: ["TechCorp"]
            - "What are our portfolio companies?" → level: "portfolio-level", keywords: ["portfolio", "companies", "investments"]"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that classifies query intent for document search."},
                    {"role": "user", "content": intent_prompt}
                ],
                max_tokens=300,
                temperature=0.1
            )
            
            # Parse JSON response
            import json
            intent_data = json.loads(response.choices[0].message.content.strip())
            logger.info(f"Query intent classified: {intent_data}")
            return intent_data
            
        except Exception as e:
            logger.error(f"Error classifying query intent: {str(e)}")
            return {
                "level": "general",
                "entities": [],
                "keywords": [],
                "exclude_keywords": []
            }

    async def _expand_query(self, query: str) -> List[str]:
        """Expand query using LLM to generate semantic variations with context awareness"""
        try:
            # First classify the query intent
            intent = await self._classify_query_intent(query)
            
            expansion_prompt = f"""You are helping with a venture capital dataroom search system. 
            Generate 2-3 different ways to ask the same question that would help find relevant information.
            
            Query intent: {intent['level']}
            Key entities: {intent['entities']}
            
            Generate variations that:
            - Use synonyms and related terms
            - Maintain the same information level ({intent['level']})
            - Include the key entities if present
            - Avoid terms that might confuse the context
            
            Original question: {query}
            
            Generate variations (one per line, no numbering):"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates query variations for document search."},
                    {"role": "user", "content": expansion_prompt}
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            # Parse the response into individual queries
            expanded_text = response.choices[0].message.content.strip()
            variations = [line.strip() for line in expanded_text.split('\n') if line.strip()]
            
            # Always include the original query
            all_queries = [query] + variations
            return all_queries[:4]  # Limit to 4 total queries
            
        except Exception as e:
            logger.error(f"Error expanding query: {str(e)}")
            return [query]  # Fallback to original query

    async def _get_relevant_context(self, queries: List[str], top_k: int) -> Tuple[List[str], List[str]]:
        """Get relevant context chunks for multiple queries with LLM-based re-ranking"""
        try:
            all_chunks = []
            all_sources = []
            seen_chunks = set()
            
            # Process each query variation
            for query in queries:
                # Embed the query
                query_embedding = await self.embedding_manager.embed_query(query)
                
                # Search the index
                scores, indices = self.index.search(query_embedding, top_k)
                
                logger.info(f"Query: '{query}' - Top scores: {scores[0][:3]}")
                
                for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                    # Lower the similarity threshold
                    if score > 0.5:  # Reduced from 0.7 to 0.5
                        chunk_metadata = self.metadata[idx]
                        
                        # Use the actual chunk text
                        chunk_text = chunk_metadata.get('chunk_text', '')
                        if chunk_text and chunk_text not in seen_chunks:
                            all_chunks.append(chunk_text)
                            seen_chunks.add(chunk_text)
                            
                            # Add source if not already added
                            file_name = chunk_metadata['file_name']
                            if file_name not in all_sources:
                                all_sources.append(file_name)
            
            # Log initial retrieval details
            logger.info(f"Retrieved {len(all_chunks)} unique chunks from {len(all_sources)} sources")
            
            # Re-rank chunks using LLM-based relevance scoring
            if all_chunks and len(queries) > 0:
                original_query = queries[0]  # Use the original query for re-ranking
                ranked_chunks = await self._rerank_chunks_with_llm(all_chunks, original_query)
                all_chunks = ranked_chunks
            
            # Log final chunks
            for i, chunk in enumerate(all_chunks[:3]):  # Log first 3 chunks
                logger.info(f"Final chunk {i+1} preview: {chunk[:100]}...")
            
            return all_chunks, all_sources
            
        except Exception as e:
            logger.error(f"Error getting relevant context: {str(e)}")
            return [], []

    async def _rerank_chunks_with_llm(self, chunks: List[str], query: str) -> List[str]:
        """Re-rank chunks using LLM-based relevance scoring"""
        try:
            if len(chunks) <= 1:
                return chunks
            
            rerank_prompt = f"""You are helping rank document chunks by relevance to a specific question.
            
            Question: "{query}"
            
            For each chunk below, rate its relevance on a scale of 0-10 where:
            - 10 = Perfectly relevant and directly answers the question
            - 7-9 = Very relevant with good information
            - 4-6 = Somewhat relevant but not directly answering
            - 1-3 = Marginally relevant
            - 0 = Not relevant or about completely different topic
            
            Consider:
            - Does the chunk directly address what's being asked?
            - Is the context appropriate (fund-level vs company-level)?
            - Does it contain the specific information requested?
            
            Chunks to rank:
            {chr(10).join([f"{i+1}. {chunk[:200]}..." for i, chunk in enumerate(chunks)])}
            
            Respond with just the scores separated by commas (e.g., "8,3,9,1,6"):"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that scores document relevance."},
                    {"role": "user", "content": rerank_prompt}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            # Parse scores
            scores_text = response.choices[0].message.content.strip()
            scores = [int(x.strip()) for x in scores_text.split(',') if x.strip().isdigit()]
            
            if len(scores) == len(chunks):
                # Create (score, chunk) pairs and sort by score descending
                scored_chunks = list(zip(scores, chunks))
                scored_chunks.sort(key=lambda x: x[0], reverse=True)
                
                logger.info(f"Re-ranking scores: {scores}")
                
                # Return only chunks with score >= 4 (somewhat relevant or better)
                filtered_chunks = [chunk for score, chunk in scored_chunks if score >= 4]
                return filtered_chunks if filtered_chunks else [chunks[0]]  # At least return the first chunk
            else:
                logger.warning(f"Score count mismatch: expected {len(chunks)}, got {len(scores)}")
                return chunks
                
        except Exception as e:
            logger.error(f"Error re-ranking chunks: {str(e)}")
            return chunks
    
    async def _generate_answer(self, question: str, context_chunks: List[str], conversation_history: List[Dict[str, str]] = None) -> str:
        """Generate an answer using GPT with context and conversation history"""
        try:
            context = "\n\n".join(context_chunks)
            
            # Build conversation messages
            messages = [
                {"role": "system", "content": """You are a helpful assistant for a venture capital dataroom. 
                Answer questions about investment strategies, portfolio companies, fund details, and other VC-related topics.
                
                CRITICAL CONTEXT DISTINCTION:
                - FUND-LEVEL information: Fund size, management fees, carried interest, investment thesis, focus areas, fund strategy
                - PORTFOLIO-LEVEL information: List of portfolio companies, portfolio construction, diversification
                - COMPANY-LEVEL information: Individual company details, their funding rounds, their investors, their metrics
                
                Guidelines:
                - Use markdown formatting for lists and structure (bullet points with - or *, numbered lists)
                - Be specific and cite relevant details from the documents
                - Carefully distinguish between fund-level and company-level information
                - If asked about "fund size", only provide information about the fund's total capital, NOT individual company round sizes
                - If asked about "investment criteria", provide the fund's criteria, NOT individual company requirements
                - If you can't find exact information, suggest related topics that might be helpful
                - Avoid saying "the documents don't contain this information" - instead suggest where to look
                - Structure answers clearly with sections when appropriate
                - Be professional and helpful to potential investors or partners
                
                VERIFICATION: Before answering, verify that the context chunks are about the correct subject level (fund vs portfolio vs company)."""}
            ]
            
            # Add conversation history if provided
            if conversation_history:
                for msg in conversation_history[-10:]:  # Limit to last 10 messages
                    messages.append(msg)
            
            # Add current question with context
            user_message = f"""Context from dataroom documents:
{context}

Question: {question}

Please provide a comprehensive answer using the context above. Use markdown formatting for lists and structure."""

            messages.append({"role": "user", "content": user_message})

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=800,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return f"Sorry, I encountered an error while generating the answer: {str(e)}"