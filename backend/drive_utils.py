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
        self.credentials = None
        self.service = None
        try:
            self._authenticate()
        except Exception as e:
            logger.error(f"Google Drive authentication failed: {e}")
            raise 

    def _authenticate(self):
        """Authenticate with Google Drive API"""
        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        token_file = GOOGLE_TOKEN_FILE or '/tmp/token.json'
        
        logger.info(f"Authenticating with token file: {token_file}")
        logger.info(f"Client ID: {GOOGLE_CLIENT_ID[:20]}...")
        
        # Check if token file exists
        if not os.path.exists(token_file):
            logger.error(f"Token file not found at {token_file}")
            raise FileNotFoundError(f"Token file not found at {token_file}")
        
        try:
            # Load existing token
            with open(token_file, 'r') as f:
                token_data = json.load(f)
                
            if not token_data or token_data == {}:
                logger.error("Empty token file found")
                raise ValueError("Empty token file")
            
            logger.info(f"Token data keys: {list(token_data.keys())}")
            
            # Create credentials from token data
            self.credentials = Credentials(
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
                scopes=SCOPES
            )
            
            logger.info(f"Created credentials with client_id: {self.credentials.client_id[:20]}...")
            
            # Refresh the token if it's expired
            if self.credentials.expired and self.credentials.refresh_token:
                logger.info("Token is expired, refreshing...")
                self.credentials.refresh(Request())
                
                # Save the refreshed token
                updated_token = {
                    'token': self.credentials.token,
                    'refresh_token': self.credentials.refresh_token,
                    'token_uri': self.credentials.token_uri,
                    'client_id': self.credentials.client_id,
                    'client_secret': self.credentials.client_secret,
                    'scopes': self.credentials.scopes
                }
                
                with open(token_file, 'w') as f:
                    json.dump(updated_token, f)
                    
                logger.info("Token refreshed and saved")
            elif self.credentials.expired:
                logger.warning("Token is expired but no refresh token available")
            
            # Build the service
            self.service = build('drive', 'v3', credentials=self.credentials)
            logger.info("Google Drive service initialized successfully")
            
        except Exception as e:
            logger.error(f"Error during authentication: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    # ... rest of your methods stay the same

    async def download_dataroom_files(self) -> List[Dict[str, Any]]:
        """Download and parse files from Google Drive dataroom folder"""
        if not self.service:
            raise ValueError("Google Drive service not initialized. Authentication may have failed.")
            
        try:
            # Find dataroom folder (you might want to specify a folder ID or name)
            # For now, we'll get all files - you can modify this to target a specific folder
            results = self.service.files().list(
                q="mimeType!='application/vnd.google-apps.folder'",
                fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)"
            ).execute()
            
            files = results.get('files', [])
            processed_files = []
            
            logger.info(f"Found {len(files)} files in Google Drive")
            
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
                return self._parse_excel_csv(file_io)
            elif mime_type.startswith('text/'):
                return file_io.read().decode('utf-8')
            else:
                logger.warning(f"Unsupported file type: {mime_type}")
                return ""
                
        except Exception as e:
            logger.error(f"Error downloading/parsing file {file['name']}: {str(e)}")
            return ""

    def _download_google_workspace_file(self, file_id: str, mime_type: str) -> str:
        """Download and convert Google Workspace files"""
        try:
            # Convert Google Docs/Sheets/Slides to text
            if mime_type == 'application/vnd.google-apps.document':
                # Export as plain text
                request = self.service.files().export_media(fileId=file_id, mimeType='text/plain')
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                # Export as CSV
                request = self.service.files().export_media(fileId=file_id, mimeType='text/csv')
            elif mime_type == 'application/vnd.google-apps.presentation':
                # Export as plain text
                request = self.service.files().export_media(fileId=file_id, mimeType='text/plain')
            else:
                logger.warning(f"Unsupported Google Workspace type: {mime_type}")
                return ""
            
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            return file_io.getvalue().decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error downloading Google Workspace file: {str(e)}")
            return ""

    def _parse_pdf(self, file_io: io.BytesIO) -> str:
        """Parse PDF content"""
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
        """Parse DOCX content"""
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
        """Parse PPTX content"""
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

    def _parse_excel_csv(self, file_io: io.BytesIO) -> str:
        """Parse Excel/CSV content"""
        try:
            df = pd.read_excel(file_io) if file_io.name.endswith('.xlsx') else pd.read_csv(file_io)
            return df.to_string()
        except Exception as e:
            logger.error(f"Error parsing Excel/CSV: {str(e)}")
            return ""


    