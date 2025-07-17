import os
import io
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]

class GoogleDriveService:
    def __init__(self):
        self.service = self._get_drive_service()

    def _get_drive_service(self):
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                script_dir = os.path.dirname(__file__)
                credentials_path = os.path.join(script_dir, "credentials.json")
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return build("drive", "v3", credentials=creds)

    def get_or_create_folder(self, folder_name, parent_folder_id=None):
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"
        else:
            query += " and 'root' in parents" # Search in root if no parent specified

        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get('files', [])
        if items:
            return items[0]['id']
        else:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_folder_id:
                file_metadata['parents'] = [parent_folder_id]
            file = self.service.files().create(body=file_metadata, fields='id').execute()
            return file.get('id')

    def list_company_folders(self):
        stock_analysis_folder_id = self.get_or_create_folder("Stock Analysis")
        if not stock_analysis_folder_id:
            return []

        company_folders = self.service.files().list(
            q=f"'{stock_analysis_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            fields="files(id, name)"
        ).execute().get('files', [])
        return company_folders

    def list_pdf_files_in_folder(self, folder_id):
        pdf_files = self.service.files().list(
            q=f"'{folder_id}' in parents and mimeType = 'application/pdf' and trashed = false",
            fields="files(id, name)"
        ).execute().get('files', [])
        return pdf_files

    def download_pdf(self, file_id, file_name):
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            # print(f"Download {int(status.progress() * 100)}%.")
        fh.seek(0)
        return fh