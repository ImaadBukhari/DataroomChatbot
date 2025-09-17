from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from typing import List, Optional
import logging

from drive_utils import GoogleDriveManager
from embed_utils import EmbeddingManager
from rag_utils import RAGManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dataroom Chatbot API")

# Add CORS middleware for browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
drive_manager = GoogleDriveManager()
embedding_manager = EmbeddingManager()
rag_manager = RAGManager(embedding_manager)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []

class UpdateResponse(BaseModel):
    status: str
    message: str
    files_processed: int = 0

@app.get("/")
async def root():
    return {"message": "Dataroom Chatbot API is running"}

@app.post("/update", response_model=UpdateResponse)
async def update_embeddings():
    """Download files from Google Drive and update embeddings"""
    try:
        logger.info("Starting dataroom update...")
        
        # Download files from Google Drive
        files = await drive_manager.download_dataroom_files()
        
        if not files:
            return UpdateResponse(
                status="success",
                message="No files found in dataroom",
                files_processed=0
            )
        
        # Process and embed files
        await embedding_manager.process_and_embed_files(files)
        
        # Update RAG manager with new embeddings
        rag_manager.load_index()
        
        logger.info(f"Successfully processed {len(files)} files")
        
        return UpdateResponse(
            status="success",
            message=f"Successfully updated embeddings for {len(files)} files",
            files_processed=len(files)
        )
        
    except Exception as e:
        logger.error(f"Error updating embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating embeddings: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Answer questions using RAG on the dataroom"""
    try:
        logger.info(f"Received chat request: {request.message}")
        
        # Get relevant context and generate response
        response, sources = await rag_manager.answer_question(request.message)
        
        return ChatResponse(
            response=response,
            sources=sources
        )
        
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")

@app.get("/status")
async def get_status():
    """Get current status of the system"""
    try:
        index_exists = embedding_manager.index_exists()
        file_count = embedding_manager.get_indexed_file_count() if index_exists else 0
        
        return {
            "index_exists": index_exists,
            "indexed_files": file_count,
            "status": "ready" if index_exists else "needs_update"
        }
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)