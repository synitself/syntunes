# Настройки UI бота

# Команда /start
START_WELCOME_TEXT = """
🎵 **Добро пожаловать в SynTunes Bot!**

Этот бот поможет создать музыкальное видео и загрузить его на YouTube.

**Как пользоваться:**
1. Отправьте аудиофайл
2. Настройте параметры (автор, название, BPM, тайп)
3. Получите готовое видео
4. Загрузите на YouTube одним кликом!

Выберите действие:
"""

# Кнопки стартового меню
BUTTON_START_SETTINGS = "⚙️ Настройки"
BUTTON_HELP = "❓ Помощь"

# Обработка аудиофайла
AUDIO_PROCESSING_TEXT = "🎵 Обрабатываю аудиофайл..."
AUDIO_PROCESSED_TEXT = """
✅ **Аудиофайл обработан!**

Настройте параметры для создания видео:
"""

# Кнопки основного меню аудиофайла
BUTTON_AUTHOR = "👤 Автор: {}"
BUTTON_TITLE = "🎵 Название: {}"
BUTTON_BPM = "🎯 BPM: {}"
BUTTON_TYPE = "🎨 Тайп: {}"
BUTTON_CREATE_VIDEO = "🎬 Создать видео"

# Кнопки навигации
BUTTON_BACK = "🔙 Назад"
BUTTON_BACK_TO_START = "🔙 Главное меню"

# Настройки (отдельное меню)
SETTINGS_TITLE = "⚙️ **Настройки**"
BUTTON_TYPES_SETTINGS = "🎨 Настройки тайпов"
BUTTON_BEATMAKERS_SETTINGS = "🎤 Битмейкеры"
BUTTON_PUBLISH_TIME = "⏰ Время публикации: {} МСК"
BUTTON_YOUTUBE_AUTH = "🔑 Авторизация YouTube"

# YouTube авторизация
YOUTUBE_AUTH_PROMPT = """
🔑 **Авторизация YouTube**

Для загрузки видео на ваш канал YouTube, пройдите авторизацию:

1. Перейдите по ссылке: {}
2. Разрешите доступ к вашему YouTube каналу
3. Скопируйте код авторизации
4. Отправьте код в этот чат

**Важно:** Видео будет загружено на ваш личный канал YouTube.
"""

YOUTUBE_AUTH_SUCCESS = "✅ YouTube авторизация успешно завершена! Теперь вы можете загружать видео на свой канал."
YOUTUBE_AUTH_ERROR = "❌ Неверный код авторизации. Попробуйте еще раз."
ERROR_YOUTUBE_AUTH = "❌ Ошибка создания ссылки авторизации."
ERROR_YOUTUBE_NOT_AUTHORIZED = "❌ Вы не авторизованы в YouTube. Пройдите авторизацию в настройках."

# Время публикации
EDIT_PUBLISH_TIME_PROMPT = "Введите время отложенной публикации видео (формат ЧЧ:ММ, МСК):"
INVALID_TIME_FORMAT = "❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 20:00)"
DEFAULT_PUBLISH_TIME = "20:00"

# Настройки тайпов
TYPES_SETTINGS_TITLE = "🎨 **Настройки тайпов**"
BUTTON_ADD_TYPE = "➕ Добавить тайп"
BUTTON_GO_TO_TYPE_SETTINGS = "⚙️ Перейти в настройки тайпов"
TYPE_NOT_SELECTED = "не выбран"

# Добавление тайпа
ADD_TYPE_NAME_PROMPT = "Введите название тайпа:"
ADD_TYPE_TAGS_PROMPT = "Введите теги для тайпа (через запятую):"
TYPE_NAME_SAVED = "✅ Название тайпа сохранено!"
TYPE_TAGS_SAVED = "✅ Теги тайпа сохранены!"
TYPE_CREATED = "✅ Тайп '{}' создан!"

# Настройки битмейкеров
BEATMAKERS_SETTINGS_TITLE = "🎤 **Битмейкеры**"
BUTTON_ADD_BEATMAKER = "➕ Добавить битмейкера"
ADD_BEATMAKER_NAME_PROMPT = "Введите имя битмейкера:"
ADD_BEATMAKER_TAG_PROMPT = "Введите YouTube тег битмейкера (например, @username):"
BEATMAKER_CREATED = "✅ Битмейкер '{}' добавлен!"

# Редактирование параметров
EDIT_AUTHOR_PROMPT = "Введите нового автора:"
EDIT_TITLE_PROMPT = "Введите новое название:"
EDIT_BPM_PROMPT = "Введите BPM (60-200):"
AUTHOR_UPDATED = "✅ Автор обновлен!"
TITLE_UPDATED = "✅ Название обновлено!"
BPM_UPDATED = "✅ BPM обновлен!"
INVALID_BPM = "❌ BPM должен быть от 60 до 200"

# Выбор тайпа
SELECT_TYPE_TITLE = "🎨 **Выберите тайп:**"
TYPE_SELECTED = "✅ Тайп '{}' выбран!"

# Создание видео
VIDEO_CREATING = "🎬 Создаю видео... Это может занять несколько минут."
VIDEO_CREATED_SCHEDULED = """
🎬 **Видео готово!**

🎤 **Автор:** {}
🎵 **Название:** {}
🎯 **BPM:** {}
🎨 **Тайп:** {}

⏰ **Запланировано к публикации {} в {} МСК**
"""

BUTTON_UPLOAD_YOUTUBE = "📤 Загрузить на YouTube"
BUTTON_RECREATE = "🔄 Пересоздать"
BUTTON_CANCEL = "❌ Отменить"

# YouTube
UPLOADING_YOUTUBE = "📤 Загружаю видео на YouTube..."
YOUTUBE_SUCCESS_SCHEDULED = """
✅ **Видео успешно загружено на YouTube!**

🔗 **Ссылка:** {}
🎤 **Автор:** {}
🎵 **Название:** {}

⏰ **Будет опубликовано {} в {} МСК**

Спасибо за использование SynTunes Bot! 🎵
"""

# Помощь
HELP_TEXT = """
📖 **Помощь**

**Основные функции:**
• Отправьте аудиофайл для создания видео
• Настройте автора, название, BPM и тайп
• Создайте и загрузите видео на YouTube

**Настройки:**
• **Тайпы** - жанры с названием и тегами
• **Битмейкеры** - соавторы с YouTube тегами
• **Время публикации** - отложенная публикация на следующий день
• **YouTube авторизация** - подключение вашего канала

**Поддерживаемые форматы:**
• MP3, FLAC, WAV, M4A

Просто отправьте аудиофайл для начала работы!
"""

# Ошибки
ERROR_PROCESSING_AUDIO = "❌ Ошибка при обработке аудиофайла. Попробуйте еще раз."
ERROR_CREATING_VIDEO = "❌ Ошибка при создании видео. Попробуйте еще раз."
ERROR_UPLOADING_YOUTUBE = "❌ Ошибка при загрузке на YouTube. Попробуйте позже."
ERROR_SESSION_EXPIRED = "❌ Сессия истекла. Начните заново с отправки аудиофайла."
ERROR_INVALID_INPUT = "❌ Неверный ввод. Попробуйте еще раз."

# Новые настройки
TRANSITION_TO_TYPE_SETTINGS = "Переход в настройки тайпов..."
PREVIEW_NOTE = "\n\n⏱️ Показаны первые 15 секунд"

# Значения по умолчанию
DEFAULT_BPM = 130
DEFAULT_AUTHOR = "syn"
DEFAULT_TYPE_NAME = "не выбран"

# Лимиты
MAX_TYPE_NAME_LENGTH = 50
MAX_TAGS_LENGTH = 200
MAX_BEATMAKER_NAME_LENGTH = 50
MAX_BEATMAKER_TAG_LENGTH = 50
MAX_AUTHOR_LENGTH = 100
MAX_TITLE_LENGTH = 200
