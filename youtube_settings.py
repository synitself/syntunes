# Настройки YouTube API

# Приватность видео
YOUTUBE_PRIVACY_STATUS = 'public'  # 'private', 'unlisted', 'public'

# Категория видео
YOUTUBE_CATEGORY_ID = '10'  # Music category

# Теги по умолчанию
YOUTUBE_DEFAULT_TAGS = [ ]

# Описание по умолчанию (шаблон)
YOUTUBE_DESCRIPTION_TEMPLATE = """
{title} βγ {artist}
{bpm} βρm
τειεgrαm : @synworks
"""

# Настройки загрузки
YOUTUBE_UPLOAD_CHUNK_SIZE = -1  # -1 для загрузки одним куском
YOUTUBE_UPLOAD_RESUMABLE = True

# Настройки обложки
YOUTUBE_UPLOAD_THUMBNAIL = True  # ВКЛЮЧЕНО после верификации
YOUTUBE_THUMBNAIL_QUALITY = 'maxresdefault'

# OAuth настройки
YOUTUBE_SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
YOUTUBE_REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'

# Файлы
YOUTUBE_TOKEN_FILE = 'token.json'
YOUTUBE_CREDENTIALS_FILE = 'client_secrets.json'