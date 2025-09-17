import os
import json
import io
from typing import List, Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import pdfplumber
from docx import Document
from pptx import Presentation
import pandas as pd
import logging

from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_TOKEN_FILE

logger = logging.getLogger(__name__)

class GoogleDriveManager:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google Drive API"""
        creds = None
        
        # Load existing token
        if os.path.exists(GOOGLE_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, self.SCOPES)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Create credentials info for OAuth flow
                client_config = {
                    "installed": {
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://localhost"]
                    }
                }
                
                flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(GOOGLE_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('drive', 'v3', credentials=creds)
        logger.info("Successfully authenticated with Google Drive")
    
    async def download_dataroom_files(self) -> List[Dict[str, Any]]:
        """Download and parse files from Google Drive dataroom folder"""
        try:
            # Find dataroom folder (you might want to specify a folder ID or name)
            # For now, we'll get all files - you can modify this to target a specific folder
            results = self.service.files().list(
                q="mimeType!='application/vnd.google-apps.folder'",
                fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)"
            ).execute()
            
            files = results.get('files', [])
            processed_files = []
            
            for file in files:
                try:
                    # Skip very large files (>50MB)
                    if file.get('size') and int(file['size']) > 50 * 1024 * 1024:
                        logger.warning(f"Skipping large file: {file['name']}")
                        continue
                    
                    content = self._download_and_parse_file(file)
                    if content:
                        processed_files.append({
                            'id': file['id'],
                            'name': file['name'],
                            'content': content,
                            'mime_type': file['mimeType'],
                            'modified_time': file.get('modifiedTime')
                        })
                        logger.info(f"Successfully processed: {file['name']}")
                    
                except Exception as e:
                    logger.error(f"Error processing file {file['name']}: {str(e)}")
                    continue
            
            logger.info(f"Successfully processed {len(processed_files)} files")
            return processed_files
            
        except Exception as e:
            logger.error(f"Error downloading files: {str(e)}")
            raise
    
    def _download_and_parse_file(self, file: Dict[str, Any]) -> str:
        """Download and parse a single file based on its type"""
        file_id = file['id']
        mime_type = file['mimeType']
        
        try:
            # Handle Google Workspace files
            if mime_type.startswith('application/vnd.google-apps'):
                return self._download_google_workspace_file(file_id, mime_type)
            
            # Handle regular files
            request = self.service.files().get_media(fileId=file_id)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            file_io.seek(0)
            
            # Parse based on file type
            if mime_type == 'application/pdf':
                return self._parse_pdf(file_io)
            elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                return self._parse_docx(file_io)
            elif mime_type == 'application/vnd.openxmlformats-officedocument.presentationml.presentation':
                return self._parse_pptx(file_io)
            elif mime_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv']:
                return self._parse_excel_csv(file_io, mime_type)
            elif mime_type.startswith('text/'):
                return file_io.read().decode('utf-8', errors='ignore')
            else:
                logger.warning(f"Unsupported file type: {mime_type}")
                return ""
                
        except Exception as e:
            logger.error(f"Error downloading/parsing file: {str(e)}")
            return ""
    
    def _download_google_workspace_file(self, file_id: str, mime_type: str) -> str:
        """Download Google Workspace files (Docs, Sheets, Slides)"""
        export_format = None
        
        if mime_type == 'application/vnd.google-apps.document':
            export_format = 'text/plain'
        elif mime_type == 'application/vnd.google-apps.spreadsheet':
            export_format = 'text/csv'
        elif mime_type == 'application/vnd.google-apps.presentation':
            export_format = 'text/plain'
        
        if export_format:
            request = self.service.files().export_media(fileId=file_id, mimeType=export_format)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            return file_io.getvalue().decode('utf-8', errors='ignore')
        
        return ""
    
    def _parse_pdf(self, file_io: io.BytesIO) -> str:
        """Parse PDF file"""
        try:
            with pdfplumber.open(file_io) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                return text
        except Exception as e:
            logger.error(f"Error parsing PDF: {str(e)}")
            return ""
    
    def _parse_docx(self, file_io: io.BytesIO) -> str:
        """Parse DOCX file"""
        try:
            doc = Document(file_io)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error parsing DOCX: {str(e)}")
            return ""
    
    def _parse_pptx(self, file_io: io.BytesIO) -> str:
        """Parse PPTX file"""
        try:
            prs = Presentation(file_io)
            text = ""
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error parsing PPTX: {str(e)}")
            return ""
    
    def _parse_excel_csv(self, file_io: io.BytesIO, mime_type: str) -> str:
        """Parse Excel or CSV file"""
        try:
            if mime_type == 'text/csv':
                df = pd.read_csv(file_io)
            else:
                df = pd.read_excel(file_io)
            
            return df.to_string()
        except Exception as e:
            logger.error(f"Error parsing Excel/CSV: {str(e)}")
            return ""