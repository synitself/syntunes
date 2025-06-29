import os
import json
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


class YouTubeUploader:
    def __init__(self, credentials_file):
        self.credentials_file = credentials_file

    def create_auth_url(self, user_id):
        """Создает URL для авторизации пользователя"""
        try:
            os.makedirs('tokens', exist_ok=True)

            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file,
                SCOPES
            )
            flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'

            auth_url, _ = flow.authorization_url(
                prompt='consent',
                access_type='offline',
                state=str(user_id)
            )

            logger.info(f"Создан URL авторизации: {auth_url}")

            with open(self.credentials_file, 'r') as f:
                client_config = json.load(f)

            flow_data = {
                'client_config': client_config,
                'scopes': SCOPES,
                'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                'state': str(user_id)
            }

            flow_file = f'tokens/flow_{user_id}.json'
            with open(flow_file, 'w') as f:
                json.dump(flow_data, f)

            return auth_url

        except Exception as e:
            logger.error(f"Ошибка создания URL авторизации: {e}")
            return None

    def complete_auth(self, user_id, auth_code):
        """Завершает авторизацию с полученным кодом"""
        try:
            flow_file = f'tokens/flow_{user_id}.json'

            if not os.path.exists(flow_file):
                logger.error(f"Файл flow не найден: {flow_file}")
                return False

            with open(flow_file, 'r') as f:
                flow_data = json.load(f)

            flow = InstalledAppFlow.from_client_config(
                flow_data['client_config'],
                flow_data['scopes']
            )
            flow.redirect_uri = flow_data['redirect_uri']

            flow.fetch_token(code=auth_code)

            token_file = f'tokens/token_{user_id}.json'
            with open(token_file, 'w') as f:
                f.write(flow.credentials.to_json())

            os.remove(flow_file)

            logger.info(f"Авторизация завершена для пользователя {user_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка завершения авторизации: {e}")
            return False

    def get_credentials(self, user_id):
        """Получает действительные учетные данные для пользователя"""
        token_file = f'tokens/token_{user_id}.json'

        creds = None
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(token_file, 'w') as f:
                        f.write(creds.to_json())
                except Exception as e:
                    logger.error(f"Ошибка обновления токена: {e}")
                    return None
            else:
                return None

        return creds

    def upload_thumbnail(self, user_id, video_id, thumbnail_path):
        """Загружает обложку для видео"""
        try:
            creds = self.get_credentials(user_id)
            if not creds:
                logger.error(f"Нет действительных учетных данных для пользователя {user_id}")
                return False

            youtube = build('youtube', 'v3', credentials=creds)

            if not os.path.exists(thumbnail_path):
                logger.error(f"Файл обложки не найден: {thumbnail_path}")
                return False

            # Проверяем размер файла (максимум 2MB)
            file_size = os.path.getsize(thumbnail_path)
            if file_size > 2 * 1024 * 1024:  # 2MB в байтах
                logger.error(f"Файл обложки слишком большой: {file_size} байт (максимум 2MB)")
                return False

            media = MediaFileUpload(
                thumbnail_path,
                mimetype='image/jpeg',
                resumable=True
            )

            request = youtube.thumbnails().set(
                videoId=video_id,
                media_body=media
            )

            response = request.execute()
            logger.info(f"Обложка успешно загружена для видео {video_id}")
            return True

        except HttpError as e:
            if e.resp.status == 400:
                logger.error(f"Ошибка загрузки обложки: аккаунт не верифицирован или неподдерживаемый формат")
            else:
                logger.error(f"HTTP ошибка при загрузке обложки: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка загрузки обложки: {e}")
            return False

    def upload_video(self, user_id, video_path, title, description="", tags=None, privacy_status="private"):
        """Загружает видео на YouTube"""
        try:
            creds = self.get_credentials(user_id)
            if not creds:
                logger.error(f"Нет действительных учетных данных для пользователя {user_id}")
                return None

            youtube = build('youtube', 'v3', credentials=creds)

            if not os.path.exists(video_path):
                logger.error(f"Файл видео не найден: {video_path}")
                return None

            tags_list = tags if tags else []

            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags_list,
                    'categoryId': '22'
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False
                }
            }

            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/*'
            )

            insert_request = youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )

            response = None
            error = None
            retry = 0

            while response is None:
                try:
                    status, response = insert_request.next_chunk()
                    if status:
                        logger.info(f"Загружено {int(status.progress() * 100)}%")
                except HttpError as e:
                    if e.resp.status in [500, 502, 503, 504]:
                        error = f"Ошибка сервера {e.resp.status}: {e}"
                        retry += 1
                        if retry > 3:
                            logger.error(f"Превышено количество попыток: {error}")
                            return None
                    else:
                        logger.error(f"HTTP ошибка: {e}")
                        return None
                except Exception as e:
                    logger.error(f"Неожиданная ошибка: {e}")
                    return None

            if response:
                video_id = response.get('id')
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                logger.info(f"Видео успешно загружено: {video_url}")

                # Пытаемся загрузить обложку
                thumbnail_path = video_path.replace('.mp4', '_thumbnail.jpg')
                if os.path.exists(thumbnail_path):
                    thumbnail_success = self.upload_thumbnail(user_id, video_id, thumbnail_path)
                    if thumbnail_success:
                        logger.info(f"Обложка успешно установлена для видео {video_id}")
                    else:
                        logger.warning(f"Не удалось установить обложку для видео {video_id}")
                else:
                    logger.warning(f"Файл обложки не найден: {thumbnail_path}")

                return {
                    'video_id': video_id,
                    'video_url': video_url,
                    'title': title
                }

        except Exception as e:
            logger.error(f"Ошибка загрузки видео: {e}")
            return None

    def is_authorized(self, user_id):
        """Проверяет, авторизован ли пользователь"""
        return self.get_credentials(user_id) is not None

    def revoke_authorization(self, user_id):
        """Отзывает авторизацию пользователя"""
        try:
            token_file = f'tokens/token_{user_id}.json'
            if os.path.exists(token_file):
                os.remove(token_file)
                logger.info(f"Авторизация отозвана для пользователя {user_id}")
                return True
        except Exception as e:
            logger.error(f"Ошибка отзыва авторизации: {e}")
        return False


def create_auth_url(credentials_file, user_id):
    """Создает URL для авторизации пользователя"""
    uploader = YouTubeUploader(credentials_file)
    return uploader.create_auth_url(user_id)


def complete_auth(credentials_file, user_id, auth_code):
    """Завершает авторизацию с полученным кодом"""
    uploader = YouTubeUploader(credentials_file)
    return uploader.complete_auth(user_id, auth_code)


def upload_video(credentials_file, user_id, video_path, title, description="", tags=None, privacy_status="private"):
    """Загружает видео на YouTube"""
    uploader = YouTubeUploader(credentials_file)
    return uploader.upload_video(user_id, video_path, title, description, tags, privacy_status)


def upload_to_youtube_scheduled(video_path, title, description="", tags=None, privacy_status="private", user_id=None):
    """Функция для запланированной загрузки видео на YouTube"""
    credentials_file = 'client_secrets.json'

    if not user_id:
        logger.error("Не указан user_id для загрузки видео")
        return None

    uploader = YouTubeUploader(credentials_file)

    if not uploader.is_authorized(user_id):
        logger.error(f"Пользователь {user_id} не авторизован")
        return None

    return uploader.upload_video(user_id, video_path, title, description, tags, privacy_status)


def is_authorized(credentials_file, user_id):
    """Проверяет, авторизован ли пользователь"""
    uploader = YouTubeUploader(credentials_file)
    return uploader.is_authorized(user_id)


def revoke_authorization(credentials_file, user_id):
    """Отзывает авторизацию пользователя"""
    uploader = YouTubeUploader(credentials_file)
    return uploader.revoke_authorization(user_id)
