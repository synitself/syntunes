import os
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import pickle
from PIL import Image, ImageDraw, ImageFont
import logging

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube']


def get_authenticated_service(credentials_file):
    creds = None
    token_file = 'token.pickle'

    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)


def get_playlist_id_by_name(youtube, playlist_name):
    """Получает ID плейлиста по названию"""
    try:
        request = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50
        )
        response = request.execute()

        for playlist in response.get('items', []):
            if playlist['snippet']['title'].lower() == playlist_name.lower():
                return playlist['id']

        logger.warning(f"Плейлист '{playlist_name}' не найден")
        return None

    except Exception as e:
        logger.error(f"Ошибка получения плейлиста: {e}")
        return None


def add_video_to_playlist(youtube, video_id, playlist_id):
    """Добавляет видео в плейлист"""
    try:
        request = youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        )
        response = request.execute()
        logger.info(f"Видео {video_id} добавлено в плейлист {playlist_id}")
        return True

    except Exception as e:
        logger.error(f"Ошибка добавления видео в плейлист: {e}")
        return False


def create_thumbnail(cover_path, output_path, bpm, artist):
    try:
        if not os.path.exists(cover_path):
            logger.warning(f"Обложка не найдена: {cover_path}")
            return None

        img = Image.open(cover_path).convert('RGB')
        img = img.resize((1280, 720), Image.Resampling.LANCZOS)

        draw = ImageDraw.Draw(img)

        try:
            font_large = ImageFont.truetype("arial.ttf", 60)
            font_medium = ImageFont.truetype("arial.ttf", 40)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()

        bpm_text = f"BPM: {bpm}"
        artist_text = f"by {artist}"

        text_bbox = draw.textbbox((0, 0), bpm_text, font=font_large)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        x = (1280 - text_width) // 2
        y = 50

        draw.rectangle([x - 10, y - 10, x + text_width + 10, y + text_height + 10], fill=(0, 0, 0, 180))
        draw.text((x, y), bpm_text, fill=(255, 255, 255), font=font_large)

        artist_bbox = draw.textbbox((0, 0), artist_text, font=font_medium)
        artist_width = artist_bbox[2] - artist_bbox[0]
        artist_height = artist_bbox[3] - artist_bbox[1]

        x_artist = (1280 - artist_width) // 2
        y_artist = 720 - artist_height - 50

        draw.rectangle([x_artist - 10, y_artist - 10, x_artist + artist_width + 10, y_artist + artist_height + 10],
                       fill=(0, 0, 0, 180))
        draw.text((x_artist, y_artist), artist_text, fill=(255, 255, 255), font=font_medium)

        img.save(output_path, 'JPEG', quality=95)
        return output_path

    except Exception as e:
        logger.error(f"Ошибка создания превью: {e}")
        return None


def upload_to_youtube_scheduled(video_path, title, description, credentials_file, thumbnail_path, bpm, artist,
                                publish_datetime_iso, playlist_name="music"):
    try:
        youtube = get_authenticated_service(credentials_file)

        tags = [f"{bpm}bpm"]

        # Получаем текущую дату в ISO формате для recordingDate
        current_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': '10',
                'defaultLanguage': 'ru'
            },
            'status': {
                'privacyStatus': 'private',
                'publishAt': publish_datetime_iso,
                'selfDeclaredMadeForKids': False,
                'embeddable': True,
                'caption': 'false'
            },
            'recordingDetails': {
                'recordingDate': current_date,
                'locationDescription': 'Студия звукозаписи'
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        insert_request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )

        video_id = None
        response = None
        error = None
        retry = 0

        while response is None:
            try:
                status, response = insert_request.next_chunk()
                if response is not None:
                    if 'id' in response:
                        video_id = response['id']
                        logger.info(f"Видео загружено с ID: {video_id}")
                    else:
                        raise Exception(f"Загрузка не удалась: {response}")
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    error = f"Ошибка сервера: {e}"
                    retry += 1
                    if retry > 3:
                        raise Exception(error)
                else:
                    raise e

        # Добавляем видео в плейлист
        if video_id and playlist_name:
            playlist_id = get_playlist_id_by_name(youtube, playlist_name)
            if playlist_id:
                add_video_to_playlist(youtube, video_id, playlist_id)
            else:
                logger.warning(f"Плейлист '{playlist_name}' не найден, видео не добавлено в плейлист")

        if video_id and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path)
                ).execute()
                logger.info("Превью загружено успешно")
            except Exception as e:
                logger.warning(f"Не удалось загрузить превью: {e}")

        video_url = f"https://www.youtube.com/watch?v={video_id}"
        return video_url

    except Exception as e:
        logger.error(f"Ошибка загрузки на YouTube: {e}")
        raise e


def upload_to_youtube(video_path, title, description, credentials_file, thumbnail_path, bpm, artist,
                      playlist_name="music"):
    try:
        youtube = get_authenticated_service(credentials_file)

        tags = [f"{bpm}bpm"]

        # Получаем текущую дату в ISO формате для recordingDate
        current_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': '10',
                'defaultLanguage': 'ru'
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False,
                'embeddable': True,
                'caption': 'false'
            },
            'recordingDetails': {
                'recordingDate': current_date,
                'locationDescription': 'Студия звукозаписи'
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        insert_request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )

        video_id = None
        response = None
        error = None
        retry = 0

        while response is None:
            try:
                status, response = insert_request.next_chunk()
                if response is not None:
                    if 'id' in response:
                        video_id = response['id']
                        logger.info(f"Видео загружено с ID: {video_id}")
                    else:
                        raise Exception(f"Загрузка не удалась: {response}")
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    error = f"Ошибка сервера: {e}"
                    retry += 1
                    if retry > 3:
                        raise Exception(error)
                else:
                    raise e

        # Добавляем видео в плейлист
        if video_id and playlist_name:
            playlist_id = get_playlist_id_by_name(youtube, playlist_name)
            if playlist_id:
                add_video_to_playlist(youtube, video_id, playlist_id)
            else:
                logger.warning(f"Плейлист '{playlist_name}' не найден, видео не добавлено в плейлист")

        thumbnail_created = create_thumbnail(
            thumbnail_path.replace('_thumbnail.jpg', '.jpg') if '_thumbnail' in thumbnail_path else thumbnail_path,
            thumbnail_path,
            bpm,
            artist
        )

        if video_id and thumbnail_created and os.path.exists(thumbnail_created):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_created)
                ).execute()
                logger.info("Превью загружено успешно")
            except Exception as e:
                logger.warning(f"Не удалось загрузить превью: {e}")

        video_url = f"https://www.youtube.com/watch?v={video_id}"
        return video_url

    except Exception as e:
        logger.error(f"Ошибка загрузки на YouTube: {e}")
        raise e
