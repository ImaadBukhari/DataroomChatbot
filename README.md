# Dataroom Chatbot

An AI-powered Chrome extension that provides intelligent search and question-answering capabilities for Google Drive dataroom documents using Retrieval-Augmented Generation (RAG).

## 🌟 Overview

The Dataroom Chatbot helps you quickly find information across multiple documents in your Google Drive by using advanced AI embeddings and natural language processing. Instead of manually searching through dozens of PDFs, spreadsheets, and presentations, simply ask questions in plain English and get accurate answers with source citations.

## 🎯 Key Features

- **Intelligent Document Search**: Uses OpenAI embeddings with advanced query decomposition to understand the semantic meaning of your questions
- **Context-Aware Retrieval**: Distinguishes between fund-level, portfolio-level, and company-specific information to avoid confusion
- **LLM-Based Re-Ranking**: Uses GPT to score and re-rank retrieved chunks for maximum relevance
- **Query Expansion**: Automatically generates semantic variations of your questions for better retrieval
- **Conversation History**: Supports follow-up questions with full conversation context
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
3. **Enhanced Chunking**: Splits documents into 300-token chunks with overlap and sentence boundary awareness
4. **Contextual Metadata**: Extracts document section context and hierarchical level tags (fund-level, company-level, etc.)
5. **Embedding Creation**: Uses OpenAI's `text-embedding-ada-002` model to create vector embeddings
6. **Index Storage**: Stores embeddings with metadata in FAISS index uploaded to Google Cloud Storage
7. **Intelligent Query Processing**: When you ask a question:
   - **Query Decomposition**: Analyzes intent and classifies information level needed
   - **Query Expansion**: Generates semantic variations while maintaining context
   - **FAISS Retrieval**: Searches for semantically similar chunks
   - **LLM Re-Ranking**: Uses GPT to score chunks for actual relevance (0-10 scale)
   - **Context Filtering**: Ensures appropriate information level (fund vs company vs portfolio)
   - **Enhanced Generation**: GPT-4 generates answers with explicit context awareness
   - **Source Citations**: Returns answer with source file references

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
Implements the advanced Retrieval-Augmented Generation logic:
- **RAGManager class**: Coordinates retrieval and generation with intelligence improvements
- `answer_question()`: Main entry point with conversation history support
- `_classify_query_intent()`: Analyzes queries to determine information level and intent
- `_expand_query()`: Generates semantic variations while maintaining context
- `_get_relevant_context()`: Searches FAISS index with multiple query variations
- `_rerank_chunks_with_llm()`: Uses GPT to score chunks for actual relevance (0-10)
- `_generate_answer()`: Uses GPT-4 with enhanced prompting for context awareness

**Enhanced Process:**
1. **Query Analysis**: Classifies intent (fund-level, company-level, portfolio-level)
2. **Query Expansion**: Generates 2-3 semantic variations maintaining context
3. **FAISS Retrieval**: Searches for chunks using all query variations
4. **LLM Re-Ranking**: GPT scores each chunk for actual relevance to the question
5. **Context Filtering**: Filters chunks by appropriate information level
6. **Enhanced Generation**: GPT-4 generates answers with explicit context distinction
7. **Source Citations**: Returns answer with source file references

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

## 🚀 Deployment & Testing

### Backend Deployment

1. **Install Dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   export GOOGLE_CLIENT_ID="your-google-client-id"
   export GOOGLE_CLIENT_SECRET="your-google-client-secret"
   export IMPERSONATED_USER="your-email@domain.com"
   ```

3. **Deploy to Cloud Run**:
   ```bash
   ./deploy.sh
   ```

4. **Update Dataroom**:
   ```bash
   curl -X POST https://your-cloud-run-url/update
   ```

### Local Testing

1. **Test with Your DDQ Document**:
   ```bash
   cd backend
   python test_rag.py
   ```

2. **Test API Endpoints**:
   ```bash
   # Health check
   curl https://your-cloud-run-url/health
   
   # Check status
   curl https://your-cloud-run-url/status
   
   # Test chat
   curl -X POST https://your-cloud-run-url/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "What is your fund size?"}'
   ```

## 📋 How to Update the Dataroom 

When you add new documents to your Google Drive dataroom, you need to update the chatbot so it can find the new information. This guide will walk you through the entire process step-by-step.

### Step 1: Open Terminal (Mac Only)

**To open Terminal on Mac:**
1. Press `Cmd + Space` (this opens Spotlight search)
2. Type "Terminal"
3. Press Enter or click on "Terminal"

You'll see a black window with text - this is your Terminal where you'll type commands.

**Note**: These instructions are for Mac. If you're on Windows, please contact your technical team for assistance.

---

### Step 2: Check if You Have Homebrew Installed (First Time Only)

Homebrew is a tool that helps install other software on Mac. Let's check if you already have it:

1. In Terminal, type this command and press Enter:
   ```bash
   which brew
   ```

2. **If you see a path** (like `/usr/local/bin/brew` or `/opt/homebrew/bin/brew`):
   - ✅ You already have Homebrew! Skip to **Step 3**.

3. **If you see nothing or an error**:
   - ❌ You need to install Homebrew. Continue to **Step 2b**.

### Step 2b: Install Homebrew (If Needed)

If you don't have Homebrew, here's how to install it:

1. Copy and paste this entire command into Terminal and press Enter:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **What's happening**: This downloads and installs Homebrew on your computer.

3. You'll be asked for your Mac password. Type it and press Enter (you won't see characters appear - this is normal for password entry).

4. Wait for the installation to finish (this takes 2-3 minutes). You'll see messages like "Installation successful" when it's done.

5. **If you see instructions about adding Homebrew to your PATH**: Follow those instructions (usually involves copying a command and running it).

---

### Step 3: Install Google Cloud CLI (First Time Only)

The Google Cloud CLI (Command Line Interface) is a tool that lets your computer talk to Google Cloud. Here's how to install it:

1. In Terminal, type this command and press Enter:
   ```bash
   brew install google-cloud-sdk
   ```

2. **What's happening**: Homebrew is downloading and installing the Google Cloud tools on your computer.

3. Wait for the installation to finish (this takes 2-5 minutes). You'll see a message like "google-cloud-sdk installed successfully" when it's done.

**Note**: You only need to do Steps 2-3 once. After that, you can skip directly to Step 4 for future updates.

---

### Step 4: Set Up Google Cloud Connection (First Time Only)

Before updating the dataroom, you need to tell your computer which Google Cloud project to use and log in. Do this:

1. **Set your Google Cloud project** - Copy and paste this command, but **replace `your-project-id`** with your actual project ID (ask your technical team if you don't know it):
   ```bash
   gcloud config set project your-project-id
   ```
   - **What's happening**: This tells the computer which Google Cloud project belongs to your dataroom.

2. Press Enter. You should see: "Updated property [core/project]"

3. **Log in to Google Cloud** - Copy and paste this command and press Enter:
   ```bash
   gcloud auth application-default login
   ```
   - **What's happening**: This opens your web browser and asks you to log in with your Google account. This gives the computer permission to access your dataroom.

4. Complete the login in your browser:
   - Select your Google account
   - Click "Allow" to grant permissions
   - You should see "Credentials saved" in your browser

5. Go back to Terminal - you should see "Credentials saved to file" message.

**Note**: You only need to do Step 4 once. After that, you can skip directly to Step 5 for future updates.

---

### Step 5: Update the Dataroom Inputs into the Chatbot

Now you're ready to update the dataroom! Here's how:

1. **Get your Cloud Run URL** - You'll need the URL of your deployed chatbot (ask your technical team if you don't have it).

2. Copy and paste this command into Terminal, but **replace `https://gcloud-url/update`** with your actual URL (it should look like `https://dataroom-chatbot-xxxxx.run.app/update`):
   ```bash
   curl -X POST https://gcloud-url/update
   ```

3. Press Enter.

4. **What's happening**: 
   - The command sends a request to your chatbot server
   - The server downloads all files from your Google Drive dataroom
   - It processes each file with AI to understand the content
   - It updates the search index so the chatbot can find information

5. **Wait 2-5 minutes** - The process takes time depending on how many documents you have. You'll see messages in Terminal as files are processed.

---

### Step 6: Check if Update Succeeded

When the update finishes, you'll see a message like this:

```json
{"status":"success","message":"Dataroom updated successfully","files_processed":47}
```

**What this means:**
- ✅ **"status":"success"** - The update worked perfectly!
- ✅ **"files_processed":47** - Your dataroom has 47 documents that are now searchable
- ✅ **Ready to use** - The chatbot now knows about all your documents

**If you see an error message instead:**
- Wait 2-3 minutes and try Step 5 again
- Check your internet connection
- If it still doesn't work, contact your technical team

---

### Step 7: Test It Works

Now test that the update worked:

1. Open your Chrome browser
2. Click on the Dataroom Chatbot extension icon
3. Ask a question about the new documents you added
4. The chatbot should be able to answer using the newly added documents!

---

### Quick Reference for Future Updates

Once you've done Steps 1-4 the first time, future updates are much simpler:

1. Open Terminal
2. Run the update command:
   ```bash
   curl -X POST https://your-actual-url/update
   ```
3. Wait for success message
4. Done!

---

### When to Update the Dataroom

Update the dataroom whenever you:
- ✅ Add new documents to your Google Drive dataroom folder
- ✅ Modify or update existing documents
- ✅ Want to ensure the chatbot has the very latest information

**Important Note**: The chatbot only searches documents in your specific Google Drive dataroom folder, not your entire Google Drive. Make sure new documents are added to the correct folder!


