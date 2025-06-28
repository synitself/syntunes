import numpy as np
from moviepy.editor import AudioFileClip, VideoClip
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
import os
import librosa
from settings import *


def get_audio_metadata(audio_path):
    """
    � звлекает метаданные из аудиофайла
    """
    try:
        from mutagen import File
        audio_file = File(audio_path)

        if audio_file is not None:
            # Получаем исполнителя
            artist = ""
            if 'TPE1' in audio_file.tags:  # MP3
                artist = str(audio_file.tags['TPE1'][0])
            elif 'ARTIST' in audio_file.tags:  # FLAC/OGG
                artist = str(audio_file.tags['ARTIST'][0])
            elif '\xa9ART' in audio_file.tags:  # MP4/M4A
                artist = str(audio_file.tags['\xa9ART'][0])

            # Получаем название
            title = ""
            if 'TIT2' in audio_file.tags:  # MP3
                title = str(audio_file.tags['TIT2'][0])
            elif 'TITLE' in audio_file.tags:  # FLAC/OGG
                title = str(audio_file.tags['TITLE'][0])
            elif '\xa9nam' in audio_file.tags:  # MP4/M4A
                title = str(audio_file.tags['\xa9nam'][0])

            # Заменяем греческую букву гамма на y
            artist = artist.replace('γ', 'y')
            title = title.replace('γ', 'y')

            return artist or "Unknown Artist", title or "Unknown Title"

    except ImportError:
        print("Для извлечения метаданных установите mutagen: pip install mutagen")
    except Exception as e:
        print(f"Ошибка при извлечении метаданных: {e}")

    return "Unknown Artist", "Unknown Title"


def load_font(size=36):
    """
    Загружает фиксированный шрифт MisterBrush.ttf
    """
    try:
        return ImageFont.truetype(FONT_FILE, size)
    except:
        print(f"Шрифт {FONT_FILE} не найден, использую стандартный")
        try:
            return ImageFont.load_default()
        except:
            return None


def create_thumbnail(image_path, output_path):
    """
    Создает обложку для YouTube: 1280x720, формат JPG
    """
    # Создаем белый фон 1280x720 (16:9)
    thumbnail = Image.new('RGB', (1280, 720), (255, 255, 255))

    # Загружаем и обрабатываем изображение
    img = Image.open(image_path).convert('RGB')

    # Масштабируем изображение под размер обложки (сохраняя пропорции)
    img.thumbnail((720, 720), Image.Resampling.LANCZOS)

    # Применяем эффект порога
    processed_img = apply_ultra_hard_threshold_effect(img, 0)

    # � азмещаем в центре
    img_width, img_height = processed_img.size
    x = (1280 - img_width) // 2
    y = (720 - img_height) // 2

    thumbnail.paste(processed_img, (x, y))

    # Сохраняем как JPG с качеством 95%
    thumbnail.save(output_path, 'JPEG', quality=95, optimize=True)
    print(f"Обложка YouTube сохранена: {output_path} (1280x720)")


def create_text_blocks(artist, title):
    """
    Создает два отдельных блока текста с улучшенной обработкой высоты
    """

    def create_single_text_block(text):
        font_size = 200
        best_font = None
        best_text_w = 0
        best_text_h = 0

        while font_size > 20:
            test_font = load_font(font_size)
            if test_font is None:
                test_font = ImageFont.load_default()

            try:
                temp_img = Image.new('RGB', (2000, 1000), (255, 255, 255))
                temp_draw = ImageDraw.Draw(temp_img)
                bbox = temp_draw.textbbox((0, 0), text, font=test_font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]

                if text_w > 0 and text_h > 0:
                    best_font = test_font
                    best_text_w = text_w
                    best_text_h = text_h
                    break
            except Exception as e:
                print(f"Ошибка с шрифтом размера {font_size}: {e}")
                pass

            font_size -= 10

        if best_font and best_text_w > 0 and best_text_h > 0:
            # Добавляем больше отступов для предотвращения обрезания
            margin_x = 60
            margin_y = 80  # Увеличенный отступ по вертикали

            temp_img = Image.new('RGB', (best_text_w + margin_x, best_text_h + margin_y), (255, 255, 255))
            temp_draw = ImageDraw.Draw(temp_img)

            # � исуем текст с увеличенными отступами
            temp_draw.text((margin_x // 2, margin_y // 2), text, fill=(0, 0, 0), font=best_font)

            # � астягиваем до нужного размера
            stretched_text = temp_img.resize((TEXT_BLOCK_WIDTH, TEXT_LINE_HEIGHT), Image.Resampling.LANCZOS)

            print(f"Блок '{text}' создан: {best_text_w}x{best_text_h} -> {TEXT_BLOCK_WIDTH}x{TEXT_LINE_HEIGHT}")
            return stretched_text
        else:
            # Fallback с увеличенными отступами
            fallback_img = Image.new('RGB', (TEXT_BLOCK_WIDTH, TEXT_LINE_HEIGHT), (255, 255, 255))
            fallback_draw = ImageDraw.Draw(fallback_img)
            fallback_font = load_font(50)
            if fallback_font is None:
                fallback_font = ImageFont.load_default()
            fallback_draw.text((20, TEXT_LINE_HEIGHT // 2 - 40), text, fill=(0, 0, 0), font=fallback_font)
            return fallback_img

    artist_block = create_single_text_block(artist)
    title_block = create_single_text_block(title)

    return artist_block, title_block


def calculate_fade_in_progress(current_time, bpm, beats_per_loop=BEATS_PER_LOOP):
    """
    Вычисляет прогресс выплывания элементов (0.0 - полностью скрыто, 1.0 - полностью видно)
    """
    beats_per_second = bpm / 60.0
    fade_duration = 8 / beats_per_second  # 8 ударов

    if current_time >= fade_duration:
        return 1.0

    return current_time / fade_duration


def apply_fade_in_effect(img, fade_progress):
    """
    Применяет эффект выплывания из белого фона
    """
    if fade_progress >= 1.0:
        return img

    # Создаем белый фон того же размера
    white_bg = Image.new('RGB', img.size, (255, 255, 255))

    # Смешиваем изображение с белым фоном
    alpha = int(fade_progress * 255)

    # Конвертируем в RGBA для альфа-смешивания
    img_rgba = img.convert('RGBA')
    white_rgba = white_bg.convert('RGBA')

    # Создаем маску альфа-канала
    alpha_mask = Image.new('L', img.size, alpha)
    img_rgba.putalpha(alpha_mask)

    # Смешиваем
    result = Image.alpha_composite(white_rgba.convert('RGBA'), img_rgba)

    return result.convert('RGB')


def apply_group_shake_effect(base_size, amplitude, group_type="default"):
    """
    Применяет эффект приближения/удаления используя настройки
    """
    if group_type == "main_image":
        multiplier = MULTIPLIER_MAIN_IMAGE
    elif group_type == "visualizations":
        multiplier = MULTIPLIER_VISUALIZATIONS
    elif group_type == "text":
        multiplier = MULTIPLIER_TEXT
    else:
        multiplier = MULTIPLIER_VISUALIZATIONS

    size_multiplier = 1.0 + amplitude * multiplier
    new_size = int(base_size * size_multiplier)
    return new_size, size_multiplier


def create_waveform_visualization(audio_data, current_time, sample_rate, width=VISUALIZATION_WIDTH,
                                  height=VISUALIZATION_HEIGHT_WAVEFORM):
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    window_size = 2.0
    current_sample = int(current_time * sample_rate)
    window_samples = int(window_size * sample_rate)

    start_sample = max(0, current_sample - window_samples // 2)
    end_sample = min(len(audio_data), current_sample + window_samples // 2)

    if end_sample > start_sample:
        waveform_data = audio_data[start_sample:end_sample]

        if len(waveform_data) > width:
            step = len(waveform_data) // width
            waveform_data = waveform_data[::step][:width]

        center_y = height // 2
        for i, sample in enumerate(waveform_data):
            y_offset = int(sample * center_y * 0.8)
            y1 = center_y - y_offset
            y2 = center_y + y_offset
            draw.line([(i, y1), (i, y2)], fill=(0, 0, 0), width=1)

        center_x = width // 2
        draw.line([(center_x, 0), (center_x, height)], fill=(255, 0, 0), width=2)

    return img


def create_spectrum_visualization(audio_data, current_time, sample_rate, width=VISUALIZATION_WIDTH,
                                  height=VISUALIZATION_HEIGHT_SPECTRUM):
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    window_samples = int(0.1 * sample_rate)
    current_sample = int(current_time * sample_rate)

    start_sample = max(0, current_sample - window_samples // 2)
    end_sample = min(len(audio_data), current_sample + window_samples // 2)

    if end_sample > start_sample:
        window_data = audio_data[start_sample:end_sample]

        windowed = window_data * np.hamming(len(window_data))
        fft = np.abs(np.fft.rfft(windowed))

        # Улучшенная обработка АЧХ для предотвращения обрезания
        if len(fft) > 0:
            # Применяем логарифмическое масштабирование с улучшенным диапазоном
            fft_db = 20 * np.log10(fft + 1e-10)

            # Адаптивная нормализация - используем процентили вместо фиксированных значений
            min_db = np.percentile(fft_db, 5)  # 5-й процентиль как минимум
            max_db = np.percentile(fft_db, 95)  # 95-й процентиль как максимум

            # � асширяем диапазон для лучшей видимости
            db_range = max_db - min_db
            if db_range > 0:
                # Нормализуем с запасом сверху и снизу
                fft_normalized = np.clip((fft_db - min_db + db_range * 0.1) / (db_range * 1.2), 0, 1)
            else:
                fft_normalized = np.zeros_like(fft_db)

            # Применяем сглаживание для более плавного отображения
            if len(fft_normalized) > 3:
                try:
                    from scipy import ndimage
                    fft_normalized = ndimage.gaussian_filter1d(fft_normalized, sigma=0.5)
                except ImportError:
                    pass  # Если scipy не установлена, пропускаем сглаживание

            # Подготавливаем данные для отображения
            if len(fft_normalized) > width:
                # Логарифмическое распределение частот для лучшего отображения
                indices = np.logspace(0, np.log10(len(fft_normalized) - 1), width).astype(int)
                fft_display = fft_normalized[indices]
            else:
                fft_display = fft_normalized

            # � исуем спектр с улучшенным масштабированием
            for i, magnitude in enumerate(fft_display):
                # � спользуем больший коэффициент высоты и добавляем минимальную высоту
                bar_height = max(int(magnitude * height * 0.95), 1)  # минимум 1 пиксель

                # � исуем от низа вверх
                y_start = height - 1
                y_end = max(0, height - bar_height)

                draw.line([(i, y_start), (i, y_end)], fill=(0, 0, 0), width=1)

    return img


def smooth_amplitudes(amplitudes, window_size=SMOOTHING_WINDOW_SIZE):
    smoothed = []
    for i in range(len(amplitudes)):
        start = max(0, i - window_size // 2)
        end = min(len(amplitudes), i + window_size // 2 + 1)
        window = amplitudes[start:end]
        smoothed.append(sum(window) / len(window))
    return smoothed


def apply_exponential_smoothing(amplitudes, alpha=SMOOTHING_ALPHA):
    if not amplitudes:
        return amplitudes

    smoothed = [amplitudes[0]]
    for i in range(1, len(amplitudes)):
        smoothed_value = alpha * amplitudes[i] + (1 - alpha) * smoothed[i - 1]
        smoothed.append(smoothed_value)

    return smoothed


def calculate_gif_timing(bpm, beats_per_loop=BEATS_PER_LOOP):
    beats_per_second = bpm / 60.0
    seconds_per_beat = 1.0 / beats_per_second
    seconds_per_loop = seconds_per_beat * beats_per_loop

    print(f"Синхронизация GIF: {beats_per_loop} ударов = {seconds_per_loop:.3f} секунд")
    return seconds_per_loop


def add_white_square_background(img, size=1080):
    width, height = img.size
    if width == height == size:
        return img

    background = Image.new('RGB', (size, size), (255, 255, 255))
    img.thumbnail((size, size), Image.Resampling.LANCZOS)

    new_width, new_height = img.size
    x = (size - new_width) // 2
    y = (size - new_height) // 2

    background.paste(img, (x, y))
    return background


def resize_gif_frame(frame, target_width=GIF_BASE_WIDTH):
    width, height = frame.size
    aspect_ratio = height / width
    target_height = int(target_width * aspect_ratio)

    return frame.resize((target_width, target_height), Image.Resampling.LANCZOS)


def load_gif_frames(target_width=GIF_BASE_WIDTH):
    """
    Загружает фиксированный GIF файл из настроек
    """
    gif_path = GIF_FILE

    if not os.path.exists(gif_path):
        print(f"GIF файл {gif_path} не найден!")
        return []

    gif = Image.open(gif_path)
    frames = []

    transparency = gif.info.get('transparency', None)

    try:
        frame_index = 0
        while True:
            frame = Image.new('RGBA', gif.size, (255, 255, 255, 255))
            current_frame = gif.copy()

            if current_frame.mode != 'RGBA':
                if 'transparency' in current_frame.info:
                    current_frame = current_frame.convert('RGBA')
                else:
                    current_frame = current_frame.convert('RGB')
                    current_frame = current_frame.convert('RGBA')

            if transparency is not None:
                data = np.array(current_frame)
                transparent_mask = data[:, :, 3] == 0
                data[transparent_mask] = [255, 255, 255, 255]
                current_frame = Image.fromarray(data)

            frame.paste(current_frame, (0, 0), current_frame)
            frame = frame.convert('RGB')
            frame = resize_gif_frame(frame, target_width)
            frames.append(frame)

            gif.seek(gif.tell() + 1)
            frame_index += 1

    except EOFError:
        pass

    return frames


def create_audio_visualizer(audio_path, image_path, output_path, bpm=BPM, beats_per_loop=BEATS_PER_LOOP):
    print("Загружаю аудио для визуализаций...")
    audio_mono, sr = librosa.load(audio_path, sr=AUDIO_SAMPLE_RATE, mono=True)

    artist, title = get_audio_metadata(audio_path)
    print(f"� сполнитель: {artist}")
    print(f"Название: {title}")
    print(f"Качество аудио: {sr} Гц")

    # Создаем обложку
    thumbnail_path = output_path.replace('.mp4', '_thumbnail.jpg')
    create_thumbnail(image_path, thumbnail_path)

    # Создаем отдельные блоки текста
    artist_block, title_block = create_text_blocks(artist, title)

    gif_loop_duration = calculate_gif_timing(bpm, beats_per_loop)

    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    fps = 30

    print("Анализ аудио...")
    amplitudes = []
    step = 1.0 / fps

    for i in range(int(duration * fps)):
        t = i * step
        try:
            start_time = max(0, t - 0.005)
            end_time = min(duration, t + 0.005)

            if end_time > start_time:
                volume = audio_clip.subclip(start_time, end_time).max_volume()
            else:
                volume = 0
            amplitudes.append(min(volume, 1.0))
        except:
            amplitudes.append(0)

    amplitudes = smooth_amplitudes(amplitudes)
    amplitudes = apply_exponential_smoothing(amplitudes)

    img = Image.open(image_path).convert('RGB')
    img = add_white_square_background(img, 1080)

    # Загружаем фиксированный GIF
    gif_frames = load_gif_frames()
    print(f"Загружено {len(gif_frames)} кадров GIF из {GIF_FILE}")

    def make_frame(t):
        frame = Image.new('RGB', (1920, 1080), (255, 255, 255))

        # Если это первые 0.2 секунды - показываем статичную обложку
        if t < 0.2:
            processed_img = apply_ultra_hard_threshold_effect(img, 0)
            img_width, img_height = processed_img.size
            x = (1920 - img_width) // 2
            y = (1080 - img_height) // 2
            frame.paste(processed_img, (x, y))
            return np.array(frame)

        frame_index = int(t * fps)
        if frame_index < len(amplitudes):
            amplitude = amplitudes[frame_index]
        else:
            amplitude = 0

        # Вычисляем прогресс выплывания (начинаем после статичной обложки)
        fade_progress = calculate_fade_in_progress(t - 0.2, bpm)

        # Группа 1: Основное изображение (всегда видно)
        main_size, main_multiplier = apply_group_shake_effect(1080, amplitude, "main_image")
        shaken_img = img.resize((main_size, main_size), Image.Resampling.LANCZOS)
        processed_img = apply_ultra_hard_threshold_effect(shaken_img, amplitude)

        img_width, img_height = processed_img.size
        x = (1920 - img_width) // 2
        y = (1080 - img_height) // 2

        frame.paste(processed_img, (x, y))

        # Группа 2: Визуализации с эффектом выплывания
        vis_size_w, vis_multiplier = apply_group_shake_effect(VISUALIZATION_WIDTH, amplitude, "visualizations")
        vis_size_h_wave = int(VISUALIZATION_HEIGHT_WAVEFORM * vis_multiplier)
        vis_size_h_spec = int(VISUALIZATION_HEIGHT_SPECTRUM * vis_multiplier)

        waveform_img = create_waveform_visualization(audio_mono, t, sr, vis_size_w, vis_size_h_wave)
        spectrum_img = create_spectrum_visualization(audio_mono, t, sr, vis_size_w, vis_size_h_spec)

        waveform_processed = apply_ultra_hard_threshold_effect(waveform_img, amplitude)
        spectrum_processed = apply_ultra_hard_threshold_effect(spectrum_img, amplitude)

        # Применяем эффект выплывания к визуализациям
        waveform_faded = apply_fade_in_effect(waveform_processed, fade_progress)
        spectrum_faded = apply_fade_in_effect(spectrum_processed, fade_progress)

        # GIF с эффектом выплывания
        current_gif_frame = None
        gif_height = vis_size_h_wave
        if gif_frames:
            cycle_position = (t % gif_loop_duration) / gif_loop_duration
            gif_frame_index = int(cycle_position * len(gif_frames)) % len(gif_frames)
            current_gif_frame = gif_frames[gif_frame_index]

            gif_w, gif_h = current_gif_frame.size
            new_gif_w = int(gif_w * vis_multiplier)
            new_gif_h = int(gif_h * vis_multiplier)
            current_gif_frame = current_gif_frame.resize((new_gif_w, new_gif_h), Image.Resampling.LANCZOS)
            gif_height = new_gif_h

        # � азмещение визуализаций
        total_height = vis_size_h_spec + 20 + vis_size_h_wave + 20 + gif_height
        center_screen = 540
        start_y = center_screen - (total_height // 2)

        vis_x = 20
        current_y = start_y

        frame.paste(spectrum_faded, (vis_x, current_y))
        current_y += vis_size_h_spec + 20

        frame.paste(waveform_faded, (vis_x, current_y))
        current_y += vis_size_h_wave + 20

        if gif_frames and current_gif_frame:
            processed_gif = apply_ultra_hard_threshold_effect(current_gif_frame, amplitude)
            gif_faded = apply_fade_in_effect(processed_gif, fade_progress)
            frame.paste(gif_faded, (vis_x, current_y))

        # Группа 3: Текстовые блоки с эффектом выплывания
        text_size_w, text_multiplier = apply_group_shake_effect(TEXT_BLOCK_WIDTH, amplitude, "text")
        text_size_h = int(TEXT_LINE_HEIGHT * text_multiplier)

        # Масштабируем блоки текста
        scaled_artist = artist_block.resize((text_size_w, text_size_h), Image.Resampling.LANCZOS)
        scaled_title = title_block.resize((text_size_w, text_size_h), Image.Resampling.LANCZOS)

        # Применяем эффект порога
        artist_processed = apply_ultra_hard_threshold_effect(scaled_artist, amplitude)
        title_processed = apply_ultra_hard_threshold_effect(scaled_title, amplitude)

        # Применяем эффект выплывания к тексту
        artist_faded = apply_fade_in_effect(artist_processed, fade_progress)
        title_faded = apply_fade_in_effect(title_processed, fade_progress)

        # Вычисляем позиции (низ видео = начало координат)
        artist_center_y_from_bottom = 145 + TEXT_LINE_HEIGHT // 2
        artist_y = 1080 - artist_center_y_from_bottom - text_size_h // 2

        title_center_y_from_bottom = 935 - TEXT_LINE_HEIGHT // 2
        title_y = 1080 - title_center_y_from_bottom - text_size_h // 2

        # X позиция справа
        text_x = 1920 - text_size_w - 20

        # � азмещаем блоки
        frame.paste(artist_faded, (text_x, artist_y))
        frame.paste(title_faded, (text_x, title_y))

        return np.array(frame)

    print("Создание видео...")
    video_clip = VideoClip(make_frame, duration=duration)
    video_clip = video_clip.set_fps(fps)

    final_clip = video_clip.set_audio(audio_clip)

    final_clip.write_videofile(output_path, codec='libx264', audio_codec='aac',
                               verbose=False, logger=None, temp_audiofile='temp-audio.m4a',
                               remove_temp=True)

    video_clip.close()
    final_clip.close()
    audio_clip.close()


def apply_ultra_hard_threshold_effect(img, amplitude):
    img_array = np.array(img)
    gray = np.dot(img_array[..., :3], [0.2989, 0.5870, 0.1140])

    threshold_value = THRESHOLD_BASE - amplitude * THRESHOLD_RANGE
    enhanced_gray = np.clip(gray * (CONTRAST_BASE + amplitude * CONTRAST_AMPLITUDE_MULTIPLIER), 0, 255)

    dark_mask = enhanced_gray < threshold_value

    result = np.full_like(img_array, 255)
    result[dark_mask] = [0, 0, 0]

    return Image.fromarray(result.astype(np.uint8))


def extract_album_art(audio_path):
    try:
        from mutagen import File
        audio_file = File(audio_path)

        if audio_file is not None:
            artwork_data = None

            if hasattr(audio_file, 'tags') and audio_file.tags:
                for key in audio_file.tags.keys():
                    if key.startswith('APIC'):
                        artwork_data = audio_file.tags[key].data
                        break

            elif hasattr(audio_file, 'pictures') and audio_file.pictures:
                artwork_data = audio_file.pictures[0].data

            if artwork_data:
                temp_cover_path = 'temp_cover.jpg'
                with open(temp_cover_path, 'wb') as f:
                    f.write(artwork_data)
                return temp_cover_path

    except ImportError:
        print("Для извлечения метаданных установите mutagen: pip install mutagen")
    except Exception as e:
        print(f"Не удалось извлечь обложку: {e}")

    return None


if __name__ == "__main__":
    print("=== АУД� ОВ� ЗУАЛ� ЗАТО�  С WAVEFORM ===")

    audio_file = input("Путь к аудиофайлу: ").strip() or AUDIO_FILE
    image_file = input("Путь к изображению (Enter для автоизвлечения): ").strip() or IMAGE_FILE
    output_file = input("� мя выходного файла (Enter = visualizer_output.mp4): ").strip() or OUTPUT_FILE

    try:
        bpm_input = input(f"BPM трека (Enter = {BPM}): ").strip()
        bpm = float(bpm_input) if bpm_input else BPM
    except ValueError:
        print(f"Неверный BPM, использую {BPM}")
        bpm = BPM

    try:
        beats_input = input(f"Количество ударов на цикл GIF (Enter = {BEATS_PER_LOOP}): ").strip()
        beats_per_loop = int(beats_input) if beats_input else BEATS_PER_LOOP
    except ValueError:
        print(f"Неверное количество ударов, использую {BEATS_PER_LOOP}")
        beats_per_loop = BEATS_PER_LOOP

    if not os.path.exists(audio_file):
        print(f"Аудиофайл не найден: {audio_file}")
        exit(1)

    if not os.path.exists(image_file):
        extracted_cover = extract_album_art(audio_file)
        if extracted_cover:
            image_file = extracted_cover
            print(f"� спользую извлеченную обложку: {extracted_cover}")
        else:
            print(f"Файл изображения не найден: {image_file}")
            exit(1)

    print(f"\nПараметры:")
    print(f"- Аудио: {audio_file}")
    print(f"- � зображение: {image_file}")
    print(f"- GIF: {GIF_FILE}")
    print(f"- Шрифт: {FONT_FILE}")
    print(f"- BPM: {bpm}")
    print(f"- Ударов на цикл: {beats_per_loop}")
    print(f"- Выходной файл: {output_file}")

    try:
        create_audio_visualizer(audio_file, image_file, output_file, bpm, beats_per_loop)
        print(f"\nГотово! Видео сохранено как: {output_file}")
    except Exception as e:
        print(f"Ошибка при создании видео: {e}")
    finally:
        if 'extracted_cover' in locals() and extracted_cover and os.path.exists(extracted_cover):
            os.remove(extracted_cover)