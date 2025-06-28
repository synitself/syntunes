# Настройки аудиовизуализатора

# Пути к файлам
AUDIO_FILE = "thirteen.mp3"
IMAGE_FILE = "cover.jpg"
GIF_FILE = "source/animation.gif"  # Фиксированный GIF
OUTPUT_FILE = "visualizer_output.mp4"

# Шрифт
FONT_FILE = "source/MisterBrush.ttf"  # Фиксированный шрифт

# Параметры визуализации
BPM = 128.0
BEATS_PER_LOOP = 8

# Качество аудио
AUDIO_SAMPLE_RATE = 48000  # 48 кГц
AUDIO_BIT_DEPTH = 24       # 24 бита

# � азмеры и отступы
TEXT_BLOCK_WIDTH = 450
TEXT_BLOCK_HEIGHT = 790
TEXT_LINE_HEIGHT = 300
TEXT_GAP_HEIGHT = 90

VISUALIZATION_WIDTH = 450
VISUALIZATION_HEIGHT_WAVEFORM = 250
VISUALIZATION_HEIGHT_SPECTRUM = 250

GIF_BASE_WIDTH = VISUALIZATION_WIDTH

# Эффекты приближения (коэффициенты)
MULTIPLIER_MAIN_IMAGE = 0.08
MULTIPLIER_VISUALIZATIONS = 0
MULTIPLIER_TEXT = 0

# Эффект порога
THRESHOLD_BASE = 240
THRESHOLD_RANGE = 240
CONTRAST_BASE = 1.5
CONTRAST_AMPLITUDE_MULTIPLIER = 2

# Сглаживание амплитуды
SMOOTHING_WINDOW_SIZE = 3
SMOOTHING_ALPHA = 0.1

