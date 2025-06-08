
import os
import io
import time
import whisper
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_account.json'

INPUT_FOLDER_NAME = 'Audio Uploads'
ARCHIVE_FOLDER_NAME = 'Audio Uploads/Audio Archive'
OUTPUT_FOLDER_NAME = 'Whisper Transcripties'
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav')

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

def get_folder_id_by_path(path):
    folders = path.split('/')
    parent_id = 'root'
    for folder in folders:
        query = f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and name = '{folder}' and trashed = false"
        results = drive_service.files().list(q=query, fields='files(id, name)').execute()
        files = results.get('files', [])
        if not files:
            raise Exception(f"Map niet gevonden: {folder}")
        parent_id = files[0]['id']
    return parent_id

input_folder_id = "1DHe2fJxPOeubsjUESlKdkm_9VUZ0mnVz"
archive_folder_id = "1ILQkCCbMxeXVLQHFX3HABKy0m7Snl6ol"
output_folder_id = "1p1GPrrAVASIVdPf0rv6D22uzrDBoycaR"

model = whisper.load_model("medium")

def process_audio_files():
    print(f"⏳ Controleren op nieuwe audiobestanden... ({datetime.datetime.now().isoformat()})")
    query = f"'{input_folder_id}' in parents and trashed = false"
    response = drive_service.files().list(q=query, fields='files(id, name)').execute()
    files = response.get('files', [])

    for file in files:
        file_id = file['id']
        file_name = file['name']
        if not file_name.lower().endswith(AUDIO_EXTENSIONS):
            continue

        print(f"📥 Downloaden: {file_name}")
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)

        local_audio = f"temp_{file_name}"
        with open(local_audio, 'wb') as f:
            f.write(fh.read())

        print(f"🎙️ Transcriberen: {file_name}")
        result = model.transcribe(local_audio, language='nl')
        transcript_text = result['text']

        transcript_name = file_name + '.txt'
        with open(transcript_name, 'w', encoding='utf-8') as f:
            f.write(transcript_text)

        media = MediaFileUpload(transcript_name, mimetype='text/plain')
        drive_service.files().create(
            body={'name': transcript_name, 'parents': [output_folder_id]},
            media_body=media
        ).execute()
        print(f"✅ Transcript opgeslagen: {transcript_name}")

        drive_service.files().update(
            fileId=file_id,
            addParents=archive_folder_id,
            removeParents=input_folder_id
        ).execute()
        print(f"📂 Verplaatst naar archief: {file_name}")

        os.remove(local_audio)
        os.remove(transcript_name)

while True:
    try:
        process_audio_files()
    except Exception as e:
        print(f"⚠️ Fout opgetreden: {e}")
    time.sleep(300)
