import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from typing import List, Optional
import logging
import sys

from drive_utils import GoogleDriveManager
from embed_utils import EmbeddingManager
from rag_utils import RAGManager

# Set up logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dataroom Chatbot API")

# Get environment variables
FRONTEND_URL = os.getenv("FRONTEND_URL", "*")
PORT = int(os.getenv("PORT", 8080))

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # More permissive for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Global variables for managers (initialize on startup)
drive_manager = None
embedding_manager = None
rag_manager = None

@app.on_event("startup")
@app.on_event("startup")
async def startup_event():
    """Initialize managers on startup"""
    global drive_manager, embedding_manager, rag_manager
    try:
        logger.info("Initializing managers...")
        
        # Check if token file exists before initializing
        token_file = '/tmp/token.json'
        if not os.path.exists(token_file):
            logger.error(f"Token file not found at {token_file}")
            return
            
        logger.info("Initializing GoogleDriveManager...")
        drive_manager = GoogleDriveManager()
        logger.info("GoogleDriveManager initialized successfully")
        
        logger.info("Initializing EmbeddingManager...")
        embedding_manager = EmbeddingManager()
        logger.info("EmbeddingManager initialized successfully")
        
        logger.info("Initializing RAGManager...")
        rag_manager = RAGManager(embedding_manager)
        logger.info("RAGManager initialized successfully")
        
        logger.info("All managers initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing managers: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Set managers to None so we know they failed
        drive_manager = None
        embedding_manager = None
        rag_manager = None

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
    return {"message": "Dataroom Chatbot API is running on Google Cloud"}

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {"status": "healthy", "port": PORT}

@app.post("/update", response_model=UpdateResponse)
async def update_embeddings():
    """Download files from Google Drive and update embeddings"""
    global drive_manager, embedding_manager, rag_manager
    
    if not drive_manager or not embedding_manager or not rag_manager:
        raise HTTPException(status_code=503, detail="Service not ready - managers not initialized")
    
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
    global rag_manager
    
    if not rag_manager:
        raise HTTPException(status_code=503, detail="Service not ready - RAG manager not initialized")
    
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
    global embedding_manager
    
    if not embedding_manager:
        return {
            "index_exists": False,
            "indexed_files": 0,
            "status": "service_starting"
        }
    
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
        return {
            "index_exists": False,
            "indexed_files": 0,
            "status": "error"
        }

@app.get("/test-drive")
async def test_drive():
    """Test Google Drive connection"""
    global drive_manager
    
    if not drive_manager:
        return {"status": "error", "message": "Drive manager not initialized"}
    
    try:
        if not drive_manager.service:
            return {"status": "error", "message": "Google Drive service not initialized"}
        
        # Test by listing first few files
        results = drive_manager.service.files().list(pageSize=5).execute()
        files = results.get('files', [])
        
        return {
            "status": "success", 
            "message": f"Found {len(files)} files",
            "files": [{"name": f['name'], "id": f['id']} for f in files]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    

@app.get("/debug-config")
async def debug_config():
    """Debug configuration"""
    import os
    from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_TOKEN_FILE
    
    return {
        "client_id_set": bool(GOOGLE_CLIENT_ID),
        "client_id_preview": GOOGLE_CLIENT_ID[:20] + "..." if GOOGLE_CLIENT_ID else "Not set",
        "client_secret_set": bool(GOOGLE_CLIENT_SECRET),
        "token_file": GOOGLE_TOKEN_FILE,
        "token_file_exists": os.path.exists(GOOGLE_TOKEN_FILE) if GOOGLE_TOKEN_FILE else False,
        "env_vars": {
            "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID", "Not set")[:20] + "..." if os.getenv("GOOGLE_CLIENT_ID") else "Not set",
            "GOOGLE_CLIENT_SECRET": "Set" if os.getenv("GOOGLE_CLIENT_SECRET") else "Not set", 
            "GOOGLE_TOKEN_FILE": os.getenv("GOOGLE_TOKEN_FILE", "Not set")
        },
        "managers_status": {
            "drive_manager": drive_manager is not None,
            "embedding_manager": embedding_manager is not None,
            "rag_manager": rag_manager is not None
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)