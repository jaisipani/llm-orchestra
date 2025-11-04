from typing import Any, Optional
from pathlib import Path
import io

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from src.utils.logger import logger

class DriveService:
    def __init__(self, credentials: Credentials):
        self.service = build('drive', 'v3', credentials=credentials)
    def search_files(
        self,
        query: Optional[str] = None,
        mime_type: Optional[str] = None,
        max_results: int = 10
    ) -> list[dict[str, Any]]:
        try:
            query_parts = []
            if query:
                query_parts.append(f"name contains '{query}'")
            
            if mime_type:
                query_parts.append(f"mimeType='{mime_type}'")
            
            query_parts.append("trashed=false")
            
            q = ' and '.join(query_parts)
            
            results = self.service.files().list(
                q=q,
                pageSize=max_results,
                fields="files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink)"
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                logger.info("No files found")
                return []
            
            logger.info(f"Found {len(files)} file(s)")
            return files
            
        except HttpError as e:
            logger.error(f"Failed to search files: {e}")
            return []
    
    def get_file(self, file_id: str) -> Optional[dict[str, Any]]:
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, createdTime, modifiedTime, size, webViewLink, parents"
            ).execute()
            return file
            
        except HttpError as e:
            logger.error(f"Failed to get file {file_id}: {e}")
            return None
    
    def upload_file(
        self,
        file_path: str,
        name: Optional[str] = None,
        folder_id: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"File not found: {file_path}")
                return None
            
            if not name:
                name = file_path_obj.name
            
            file_metadata = {'name': name}
            
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            media = MediaFileUpload(file_path, mimetype=mime_type)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()
            
            logger.info(f"File uploaded: {name}")
            logger.debug(f"File ID: {file['id']}")
            
            return file
            
        except HttpError as e:
            logger.error(f"Failed to upload file: {e}")
            return None
    
    def download_file(
        self,
        file_id: str,
        destination: str
    ) -> bool:
        try:
            request = self.service.files().get_media(fileId=file_id)
            fh = io.FileIO(destination, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.debug(f"Download progress: {progress}%")
            
            logger.info(f"File downloaded to: {destination}")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to download file: {e}")
            return False
    
    def share_file(
        self,
        file_id: str,
        email: str,
        role: str = 'reader'
    ) -> bool:
        try:
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            self.service.permissions().create(
                fileId=file_id,
                body=permission,
                sendNotificationEmail=True,
                fields='id'
            ).execute()
            
            logger.info(f"File {file_id} shared with {email} ({role})")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to share file: {e}")
            return False
    
    def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id, name, webViewLink'
            ).execute()
            
            logger.info(f"Folder created: {name}")
            logger.debug(f"Folder ID: {folder['id']}")
            
            return folder
            
        except HttpError as e:
            logger.error(f"Failed to create folder: {e}")
            return None
    
    def delete_file(self, file_id: str) -> bool:
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"File deleted: {file_id}")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False
    
    def move_file(
        self,
        file_id: str,
        new_folder_id: str
    ) -> bool:
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='parents'
            ).execute()
            previous_parents = ','.join(file.get('parents', []))
            
            self.service.files().update(
                fileId=file_id,
                addParents=new_folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            
            logger.info(f"File {file_id} moved to folder {new_folder_id}")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to move file: {e}")
            return False
    
    def list_recent_files(self, max_results: int = 10) -> list[dict[str, Any]]:
        try:
            results = self.service.files().list(
                pageSize=max_results,
                orderBy='modifiedTime desc',
                q="trashed=false",
                fields="files(id, name, mimeType, modifiedTime, webViewLink)"
            ).execute()
            files = results.get('files', [])
            
            logger.info(f"Found {len(files)} recent file(s)")
            return files
            
        except HttpError as e:
            logger.error(f"Failed to list recent files: {e}")
            return []
