# Dataroom Chatbot

An AI-powered Chrome extension that provides intelligent search and question-answering capabilities for Google Drive dataroom documents using Retrieval-Augmented Generation (RAG).

## 🌟 Overview

The Dataroom Chatbot helps you quickly find information across multiple documents in your Google Drive by using advanced AI embeddings and natural language processing. Instead of manually searching through dozens of PDFs, spreadsheets, and presentations, simply ask questions in plain English and get accurate answers with source citations.

## 🎯 Key Features

- **Intelligent Document Search**: Uses OpenAI embeddings to understand the semantic meaning of your questions
- **Multi-Format Support**: Processes PDFs, Word docs, PowerPoint presentations, Excel spreadsheets, and Google Workspace files
- **Source Citations**: Every answer includes references to the source documents
- **Persistent Storage**: Embeddings are stored in Google Cloud Storage for fast retrieval
- **Chrome Extension Interface**: Convenient popup interface accessible from any webpage
- **Cloud-Hosted Backend**: Scalable FastAPI backend deployed on Google Cloud Run

## 🏗️ Architecture

```
┌─────────────────┐
│  Chrome Popup   │ ← User Interface
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────┐
│  Cloud Run API  │ ← FastAPI Backend
└────────┬────────┘
         │
    ┌────┴─────┬──────────┬───────────┐
    ▼          ▼          ▼           ▼
┌────────┐ ┌──────┐ ┌──────────┐ ┌────────┐
│ Drive  │ │OpenAI│ │  Cloud   │ │ FAISS  │
│  API   │ │ API  │ │ Storage  │ │ Index  │
└────────┘ └──────┘ └──────────┘ └────────┘
```

### How It Works

1. **Document Ingestion**: Downloads files from your Google Drive
2. **Text Extraction**: Parses various file formats into plain text
3. **Chunking**: Splits documents into 300-token chunks for optimal embedding
4. **Embedding Creation**: Uses OpenAI's `text-embedding-ada-002` model to create vector embeddings
5. **Index Storage**: Stores embeddings in FAISS index uploaded to Google Cloud Storage
6. **Query Processing**: When you ask a question:
   - Creates an embedding of your question
   - Searches FAISS index for semantically similar chunks
   - Sends relevant context to GPT-4 for answer generation
   - Returns answer with source citations

## 📁 Project Structure

```
DataroomChatbot/
├── backend/                    # FastAPI backend application
│   ├── app.py                 # Main API endpoints and server
│   ├── drive_utils.py         # Google Drive integration
│   ├── embed_utils.py         # Embedding creation and management
│   ├── rag_utils.py           # RAG logic and answer generation
│   ├── config.py              # Configuration and environment variables
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile            # Container configuration
│
├── extension/                 # Chrome extension frontend
│   ├── manifest.json         # Extension configuration
│   ├── popup.html            # Extension UI structure
│   ├── popup.js              # Extension logic and API calls
│   └── styles.css            # Extension styling
│
└── deploy.sh                 # Deployment script for Google Cloud Run
```

## 🔑 Key Files Explained

### Backend Files

#### `backend/app.py`
The main FastAPI application that handles all API endpoints:
- `/health` - Health check for Cloud Run
- `/status` - Returns indexing status and file count
- `/update` - Triggers dataroom update and re-indexing
- `/chat` - Processes questions and returns AI-generated answers
- `/test-drive` - Debug endpoint to verify Google Drive connection

**Key responsibilities:**
- Initializes all managers on startup
- Handles CORS for cross-origin requests
- Manages error handling and logging
- Coordinates between Drive, Embedding, and RAG managers

#### `backend/drive_utils.py`
Manages all Google Drive interactions:
- **GoogleDriveManager class**: Handles authentication and file operations
- `_authenticate()`: Authenticates using OAuth2 credentials
- `download_dataroom_files()`: Lists and downloads files from Drive
- `_download_and_parse_file()`: Routes files to appropriate parsers
- `_parse_pdf()`, `_parse_docx()`, etc.: Extract text from various formats

**Supported formats:**
- PDF (via pdfplumber)
- Word documents (via python-docx)
- PowerPoint (via python-pptx)
- Excel/CSV (via pandas)
- Google Docs, Sheets, Slides (via Drive API export)

#### `backend/embed_utils.py`
Handles embedding creation and storage:
- **EmbeddingManager class**: Manages the embedding lifecycle
- `process_and_embed_files()`: Main workflow for creating embeddings
- `_split_into_chunks()`: Breaks text into 300-token chunks
- `_create_embeddings()`: Calls OpenAI API to create embeddings
- `_create_and_save_index()`: Creates FAISS index and uploads to Cloud Storage
- `load_index()`: Downloads index from Cloud Storage
- `embed_query()`: Creates embedding for user questions

**Key features:**
- Persistent storage in Google Cloud Storage
- Batch processing for API efficiency
- Automatic index normalization for cosine similarity

#### `backend/rag_utils.py`
Implements the Retrieval-Augmented Generation logic:
- **RAGManager class**: Coordinates retrieval and generation
- `answer_question()`: Main entry point for question answering
- `_get_relevant_context()`: Searches FAISS index for relevant chunks
- `_generate_answer()`: Uses GPT-4 to generate answers from context

**Process:**
1. Embeds the user's question
2. Searches FAISS index for top-k similar chunks (default: 5)
3. Filters by similarity threshold (0.5)
4. Sends relevant chunks + question to GPT-4
5. Returns answer with source file citations

### Frontend Files

#### `extension/manifest.json`
Chrome extension configuration:
- Defines extension name, version, and permissions
- Configures OAuth2 client ID for authentication
- Sets up the popup interface

#### `extension/popup.html`
Extension user interface structure:
- Header with status indicator
- "Update Dataroom" button
- Chat message container
- Message input and send button
- File count footer

#### `extension/popup.js`
Extension logic and API communication:
- **DataroomChatbot class**: Manages all extension functionality
- `checkStatus()`: Polls backend for indexing status
- `updateDataroom()`: Triggers document re-indexing
- `sendMessage()`: Sends questions to backend
- `addMessage()`: Displays messages in chat UI

**Features:**
- Real-time status updates
- Loading states and error handling
- Message history in popup
- Automatic scrolling

#### `extension/styles.css`
Modern, professional styling:
- Gradient background with animation
- Glass-morphism effects
- Smooth transitions and hover effects
- Responsive message bubbles
- Color-coded status indicators
