import os
import asyncio
import re
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, \
    ConversationHandler
from telegram.constants import ParseMode
import logging
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

from processor import create_audio_visualizer, get_audio_metadata, extract_album_art, add_white_square_background, \
    apply_ultra_hard_threshold_effect
from youtube_uploader import upload_to_youtube_scheduled
from bot_settings import *
from settings import *
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

(START_MENU, MAIN_MENU, EDIT_AUTHOR, EDIT_TITLE, EDIT_BPM, SETTINGS_MENU,
 TYPES_SETTINGS, ADD_TYPE_NAME, ADD_TYPE_TAGS, BEATMAKERS_SETTINGS,
 ADD_BEATMAKER_NAME, ADD_BEATMAKER_TAG, EDIT_PUBLISH_TIME) = range(13)


class SyntunesBot:
    def __init__(self, token, youtube_credentials):
        self.token = token
        self.youtube_credentials = youtube_credentials
        self.user_sessions = {}
        self.db = Database()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username

        self.db.add_user(user_id, username)

        if update.message:
            try:
                await update.message.delete()
            except:
                pass

        keyboard = [
            [InlineKeyboardButton(BUTTON_START_SETTINGS, callback_data="start_settings")],
            [InlineKeyboardButton(BUTTON_HELP, callback_data="help")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            START_WELCOME_TEXT,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

        return START_MENU

    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        await self.cleanup_user_messages(user_id, context)

        processing_msg = await update.message.reply_text(AUDIO_PROCESSING_TEXT)

        try:
            audio_file = await update.message.audio.get_file()
            user_dir = f"temp_user_{user_id}_{int(asyncio.get_event_loop().time())}"
            os.makedirs(user_dir, exist_ok=True)

            audio_path = f"{user_dir}/audio.mp3"
            await audio_file.download_to_drive(audio_path)

            artist, title = get_audio_metadata(audio_path)
            cover_path = extract_album_art(audio_path)

            self.user_sessions[user_id] = {
                'audio_path': audio_path,
                'cover_path': cover_path,
                'original_artist': artist,
                'original_title': title,
                'current_artist': artist,
                'current_title': title,
                'current_bpm': DEFAULT_BPM,
                'current_type': None,
                'user_dir': user_dir,
                'step': 'main_menu',
                'processing_message_id': None
            }

            await self.show_audio_menu(update, context, user_id)

        except Exception as e:
            logger.error(f"Ошибка обработки аудио: {e}")
            await processing_msg.edit_text(ERROR_PROCESSING_AUDIO)
            return ConversationHandler.END
        finally:
            try:
                await processing_msg.delete()
            except:
                pass

        return MAIN_MENU

    def parse_collaborators_from_author_tag(self, author_tag, user_id):
        """
        Парсит тег автора, разделенный запятыми, исключает 'syn' и возвращает список коллабораторов
        """
        if not author_tag:
            return []

        authors = [a.strip() for a in author_tag.split(',') if a.strip()]
        collaborators = [a for a in authors if a.lower() != 'syn']

        return collaborators

    def create_telegram_cover(self, image_path, output_path):
        cover = Image.new('RGB', (1080, 1080), (255, 255, 255))
        img = Image.open(image_path).convert('RGB')
        img = add_white_square_background(img, 1080)
        processed_img = apply_ultra_hard_threshold_effect(img, 0)

        img_width, img_height = processed_img.size
        x = (1080 - img_width) // 2
        y = (1080 - img_height) // 2

        cover.paste(processed_img, (x, y))
        cover.save(output_path, 'JPEG', quality=95, optimize=True)
        return output_path

    def create_preview_video(self, input_path, output_path):
        from moviepy.editor import VideoFileClip
        video = VideoFileClip(input_path)
        preview = video.subclip(0, min(15, video.duration))
        preview.write_videofile(output_path, codec='libx264', audio_codec='aac', verbose=False, logger=None)
        video.close()
        preview.close()

    async def show_audio_menu(self, update, context, user_id):
        session = self.user_sessions[user_id]

        keyboard = [
            [InlineKeyboardButton(
                BUTTON_AUTHOR.format(
                    session['current_artist'][:20] + "..." if len(session['current_artist']) > 20 else session[
                        'current_artist']),
                callback_data="edit_author"
            )],
            [InlineKeyboardButton(
                BUTTON_TITLE.format(
                    session['current_title'][:20] + "..." if len(session['current_title']) > 20 else session[
                        'current_title']),
                callback_data="edit_title"
            )],
            [InlineKeyboardButton(
                BUTTON_BPM.format(session['current_bpm']),
                callback_data="edit_bpm"
            )],
            [InlineKeyboardButton(
                BUTTON_TYPE.format(session['current_type'] or DEFAULT_TYPE_NAME),
                callback_data="select_type"
            )],
            [InlineKeyboardButton(BUTTON_CREATE_VIDEO, callback_data="create_video")],
            [InlineKeyboardButton(BUTTON_CANCEL, callback_data="cancel_audio")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        if session['cover_path'] and os.path.exists(session['cover_path']):
            telegram_cover_path = f"{session['user_dir']}/telegram_cover.jpg"
            self.create_telegram_cover(session['cover_path'], telegram_cover_path)

            msg = await context.bot.send_photo(
                chat_id=user_id,
                photo=open(telegram_cover_path, 'rb'),
                caption=AUDIO_PROCESSED_TEXT,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            msg = await context.bot.send_message(
                chat_id=user_id,
                text=AUDIO_PROCESSED_TEXT,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        session['main_menu_message_id'] = msg.message_id

    async def show_settings_menu(self, query, context, user_id):
        publish_time = self.db.get_scheduled_publish_time(user_id) or DEFAULT_PUBLISH_TIME

        keyboard = [
            [InlineKeyboardButton(BUTTON_TYPES_SETTINGS, callback_data="types_settings")],
            [InlineKeyboardButton(BUTTON_BEATMAKERS_SETTINGS, callback_data="beatmakers_settings")],
            [InlineKeyboardButton(BUTTON_PUBLISH_TIME.format(publish_time), callback_data="edit_publish_time")],
            [InlineKeyboardButton(BUTTON_BACK_TO_START, callback_data="back_to_start")]
        ]

        await query.edit_message_text(
            text=SETTINGS_TITLE,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

        return SETTINGS_MENU

    async def show_types_settings(self, query, context, user_id):
        user_types = self.db.get_user_types(user_id)
        keyboard = []

        for type_name in user_types:
            keyboard.append([InlineKeyboardButton(f"🎨 {type_name}", callback_data=f"edit_type_{type_name}")])

        keyboard.append([InlineKeyboardButton(BUTTON_ADD_TYPE, callback_data="add_type")])
        keyboard.append([InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_settings")])

        await query.edit_message_text(
            text=TYPES_SETTINGS_TITLE,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

        return TYPES_SETTINGS

    async def show_beatmakers_settings(self, query, context, user_id):
        user_beatmakers = self.db.get_user_beatmakers(user_id)
        keyboard = []

        for beatmaker_data in user_beatmakers:
            name = beatmaker_data['name']
            tag = beatmaker_data['tag']
            keyboard.append([InlineKeyboardButton(f"🎤 {name} : {tag}", callback_data=f"edit_beatmaker_{name}")])

        keyboard.append([InlineKeyboardButton(BUTTON_ADD_BEATMAKER, callback_data="add_beatmaker")])
        keyboard.append([InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_settings")])

        await query.edit_message_text(
            text=BEATMAKERS_SETTINGS_TITLE,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

        return BEATMAKERS_SETTINGS

    async def show_type_selection(self, query, context, user_id):
        user_types = self.db.get_user_types(user_id)
        keyboard = []

        for type_name in user_types:
            keyboard.append([InlineKeyboardButton(type_name, callback_data=f"type_{type_name}")])

        keyboard.append([InlineKeyboardButton(BUTTON_GO_TO_TYPE_SETTINGS, callback_data="go_to_type_settings")])
        keyboard.append([InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_audio")])

        await query.edit_message_caption(
            caption=SELECT_TYPE_TITLE,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

        return MAIN_MENU

    async def handle_start_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        data = query.data

        if data == "start_settings":
            return await self.show_settings_menu(query, context, user_id)
        elif data == "help":
            await query.edit_message_text(
                text=HELP_TEXT,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(BUTTON_BACK_TO_START, callback_data="back_to_start")]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return START_MENU
        elif data == "back_to_start":
            keyboard = [
                [InlineKeyboardButton(BUTTON_START_SETTINGS, callback_data="start_settings")],
                [InlineKeyboardButton(BUTTON_HELP, callback_data="help")]
            ]

            await query.edit_message_text(
                text=START_WELCOME_TEXT,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            return START_MENU

        return START_MENU

    async def handle_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        data = query.data

        if data == "types_settings":
            return await self.show_types_settings(query, context, user_id)
        elif data == "beatmakers_settings":
            return await self.show_beatmakers_settings(query, context, user_id)
        elif data == "edit_publish_time":
            await query.edit_message_text(
                text=EDIT_PUBLISH_TIME_PROMPT,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_settings")]])
            )

            context.user_data['prompt_message_id'] = query.message.message_id
            context.user_data['current_state'] = EDIT_PUBLISH_TIME
            return EDIT_PUBLISH_TIME
        elif data == "back_to_settings":
            return await self.show_settings_menu(query, context, user_id)
        elif data == "back_to_start":
            keyboard = [
                [InlineKeyboardButton(BUTTON_START_SETTINGS, callback_data="start_settings")],
                [InlineKeyboardButton(BUTTON_HELP, callback_data="help")]
            ]

            await query.edit_message_text(
                text=START_WELCOME_TEXT,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            return START_MENU
        elif data == "add_type":
            msg = await query.edit_message_text(
                text=ADD_TYPE_NAME_PROMPT,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_settings")]])
            )

            context.user_data['prompt_message_id'] = msg.message_id
            context.user_data['current_state'] = ADD_TYPE_NAME
            return ADD_TYPE_NAME
        elif data == "add_beatmaker":
            msg = await query.edit_message_text(
                text=ADD_BEATMAKER_NAME_PROMPT,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_settings")]])
            )

            context.user_data['prompt_message_id'] = msg.message_id
            context.user_data['current_state'] = ADD_BEATMAKER_NAME
            return ADD_BEATMAKER_NAME

        return SETTINGS_MENU

    async def handle_audio_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        data = query.data

        if user_id not in self.user_sessions:
            await query.edit_message_text(ERROR_SESSION_EXPIRED)
            return ConversationHandler.END

        session = self.user_sessions[user_id]

        if data == "cancel_audio":
            self.cleanup_session(user_id)
            try:
                await query.message.delete()
            except:
                pass
            return ConversationHandler.END
        elif data == "edit_author":
            await query.edit_message_caption(
                caption=EDIT_AUTHOR_PROMPT,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_audio")]])
            )

            context.user_data['current_state'] = EDIT_AUTHOR
            return EDIT_AUTHOR
        elif data == "edit_title":
            await query.edit_message_caption(
                caption=EDIT_TITLE_PROMPT,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_audio")]])
            )

            context.user_data['current_state'] = EDIT_TITLE
            return EDIT_TITLE
        elif data == "edit_bpm":
            await query.edit_message_caption(
                caption=EDIT_BPM_PROMPT,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_audio")]])
            )

            context.user_data['current_state'] = EDIT_BPM
            return EDIT_BPM
        elif data == "select_type":
            return await self.show_type_selection(query, context, user_id)
        elif data == "create_video":
            return await self.create_video(query, context, user_id)
        elif data == "back_to_audio":
            await self.update_audio_menu(query, context, user_id)
            return MAIN_MENU
        elif data.startswith("type_"):
            type_name = data[5:]
            session['current_type'] = type_name
            await self.update_audio_menu(query, context, user_id)
            return MAIN_MENU
        elif data == "go_to_type_settings":
            try:
                await query.message.delete()
            except:
                pass

            msg = await context.bot.send_message(
                chat_id=user_id,
                text=TRANSITION_TO_TYPE_SETTINGS
            )

            from types import SimpleNamespace
            new_query = SimpleNamespace()
            new_query.message = msg
            new_query.edit_message_text = msg.edit_text

            return await self.show_types_settings(new_query, context, user_id)
        elif data == "upload_youtube":
            return await self.upload_to_youtube(query, context, user_id)
        elif data == "recreate_video":
            return await self.create_video(query, context, user_id)

        return MAIN_MENU

    async def update_audio_menu(self, query, context, user_id):
        session = self.user_sessions[user_id]

        keyboard = [
            [InlineKeyboardButton(
                BUTTON_AUTHOR.format(
                    session['current_artist'][:20] + "..." if len(session['current_artist']) > 20 else session[
                        'current_artist']),
                callback_data="edit_author"
            )],
            [InlineKeyboardButton(
                BUTTON_TITLE.format(
                    session['current_title'][:20] + "..." if len(session['current_title']) > 20 else session[
                        'current_title']),
                callback_data="edit_title"
            )],
            [InlineKeyboardButton(
                BUTTON_BPM.format(session['current_bpm']),
                callback_data="edit_bpm"
            )],
            [InlineKeyboardButton(
                BUTTON_TYPE.format(session['current_type'] or DEFAULT_TYPE_NAME),
                callback_data="select_type"
            )],
            [InlineKeyboardButton(BUTTON_CREATE_VIDEO, callback_data="create_video")],
            [InlineKeyboardButton(BUTTON_CANCEL, callback_data="cancel_audio")]
        ]

        await query.edit_message_caption(
            caption=AUDIO_PROCESSED_TEXT,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()

        try:
            await update.message.delete()
        except:
            pass

        current_state = context.user_data.get('current_state')

        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]

            if current_state == EDIT_AUTHOR:
                if len(text) <= MAX_AUTHOR_LENGTH:
                    session['current_artist'] = text
                    await self.update_audio_menu_after_edit(context, user_id)
                else:
                    await self.send_temp_message(context, user_id, ERROR_INVALID_INPUT)
                return MAIN_MENU
            elif current_state == EDIT_TITLE:
                if len(text) <= MAX_TITLE_LENGTH:
                    session['current_title'] = text
                    await self.update_audio_menu_after_edit(context, user_id)
                else:
                    await self.send_temp_message(context, user_id, ERROR_INVALID_INPUT)
                return MAIN_MENU
            elif current_state == EDIT_BPM:
                try:
                    bpm = float(text)
                    if 60 <= bpm <= 200:
                        session['current_bpm'] = bpm
                        await self.update_audio_menu_after_edit(context, user_id)
                    else:
                        await self.send_temp_message(context, user_id, INVALID_BPM)
                except ValueError:
                    await self.send_temp_message(context, user_id, INVALID_BPM)
                return MAIN_MENU

        if current_state == EDIT_PUBLISH_TIME:
            if self.validate_time_format(text):
                self.db.set_scheduled_publish_time(user_id, text)

                try:
                    await context.bot.delete_message(
                        chat_id=user_id,
                        message_id=context.user_data['prompt_message_id']
                    )
                except:
                    pass

                await self.show_settings_menu_after_time_update(context, user_id)
                return SETTINGS_MENU
            else:
                await self.send_temp_message(context, user_id, INVALID_TIME_FORMAT)
                return EDIT_PUBLISH_TIME
        elif current_state == ADD_TYPE_NAME:
            if len(text) <= MAX_TYPE_NAME_LENGTH:
                context.user_data['new_type_name'] = text

                try:
                    await context.bot.delete_message(
                        chat_id=user_id,
                        message_id=context.user_data['prompt_message_id']
                    )
                except:
                    pass

                msg = await context.bot.send_message(
                    chat_id=user_id,
                    text=ADD_TYPE_TAGS_PROMPT,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_settings")]])
                )

                context.user_data['prompt_message_id'] = msg.message_id
                context.user_data['current_state'] = ADD_TYPE_TAGS
                return ADD_TYPE_TAGS
            else:
                await self.send_temp_message(context, user_id, ERROR_INVALID_INPUT)
                return ADD_TYPE_NAME
        elif current_state == ADD_TYPE_TAGS:
            if len(text) <= MAX_TAGS_LENGTH:
                type_name = context.user_data.get('new_type_name')
                self.db.add_user_type(user_id, type_name, text)

                try:
                    await context.bot.delete_message(
                        chat_id=user_id,
                        message_id=context.user_data['prompt_message_id']
                    )
                except:
                    pass

                await context.bot.send_message(
                    chat_id=user_id,
                    text=TYPE_CREATED.format(type_name),
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_settings")]])
                )

                context.user_data.pop('new_type_name', None)
                context.user_data.pop('prompt_message_id', None)
                return SETTINGS_MENU
            else:
                await self.send_temp_message(context, user_id, ERROR_INVALID_INPUT)
                return ADD_TYPE_TAGS
        elif current_state == ADD_BEATMAKER_NAME:
            if len(text) <= MAX_BEATMAKER_NAME_LENGTH:
                context.user_data['new_beatmaker_name'] = text

                try:
                    await context.bot.delete_message(
                        chat_id=user_id,
                        message_id=context.user_data['prompt_message_id']
                    )
                except:
                    pass

                msg = await context.bot.send_message(
                    chat_id=user_id,
                    text=ADD_BEATMAKER_TAG_PROMPT,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_settings")]])
                )

                context.user_data['prompt_message_id'] = msg.message_id
                context.user_data['current_state'] = ADD_BEATMAKER_TAG
                return ADD_BEATMAKER_TAG
            else:
                await self.send_temp_message(context, user_id, ERROR_INVALID_INPUT)
                return ADD_BEATMAKER_NAME
        elif current_state == ADD_BEATMAKER_TAG:
            if len(text) <= MAX_BEATMAKER_TAG_LENGTH:
                beatmaker_name = context.user_data.get('new_beatmaker_name')
                self.db.add_user_beatmaker(user_id, beatmaker_name, text)

                try:
                    await context.bot.delete_message(
                        chat_id=user_id,
                        message_id=context.user_data['prompt_message_id']
                    )
                except:
                    pass

                await context.bot.send_message(
                    chat_id=user_id,
                    text=BEATMAKER_CREATED.format(beatmaker_name),
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_settings")]])
                )

                context.user_data.pop('new_beatmaker_name', None)
                context.user_data.pop('prompt_message_id', None)
                return SETTINGS_MENU
            else:
                await self.send_temp_message(context, user_id, ERROR_INVALID_INPUT)
                return ADD_BEATMAKER_TAG

        return MAIN_MENU

    def validate_time_format(self, time_str):
        """Проверяет формат времени ЧЧ:ММ"""
        try:
            time_parts = time_str.split(':')
            if len(time_parts) != 2:
                return False

            hours = int(time_parts[0])
            minutes = int(time_parts[1])

            return 0 <= hours <= 23 and 0 <= minutes <= 59
        except ValueError:
            return False

    def convert_msk_to_utc_iso(self, time_str, user_id):
        """Конвертирует время МСК в UTC ISO формат для следующего доступного дня"""
        try:
            msk_tz = pytz.timezone('Europe/Moscow')
            utc_tz = pytz.UTC

            # Получаем следующую доступную дату
            available_date_str = self.db.get_next_available_date(user_id, time_str)
            available_date = datetime.strptime(available_date_str, '%Y-%m-%d').date()

            # Парсим время
            hours, minutes = map(int, time_str.split(':'))

            # Создаем datetime объект для доступного дня в МСК
            msk_datetime = msk_tz.localize(
                datetime.combine(available_date, datetime.min.time().replace(hour=hours, minute=minutes)))

            # Конвертируем в UTC
            utc_datetime = msk_datetime.astimezone(utc_tz)

            # Сохраняем информацию о запланированной публикации
            video_title = f"{self.user_sessions[user_id]['current_artist']} - {self.user_sessions[user_id]['current_title']}"
            self.db.add_scheduled_upload(user_id, video_title, available_date_str, time_str)

            # Возвращаем в ISO формате
            return utc_datetime.strftime('%Y-%m-%dT%H:%M:%S.000Z'), available_date_str
        except Exception as e:
            logger.error(f"Ошибка конвертации времени: {e}")
            return None, None

    async def show_settings_menu_after_time_update(self, context, user_id):
        publish_time = self.db.get_scheduled_publish_time(user_id) or DEFAULT_PUBLISH_TIME

        keyboard = [
            [InlineKeyboardButton(BUTTON_TYPES_SETTINGS, callback_data="types_settings")],
            [InlineKeyboardButton(BUTTON_BEATMAKERS_SETTINGS, callback_data="beatmakers_settings")],
            [InlineKeyboardButton(BUTTON_PUBLISH_TIME.format(publish_time), callback_data="edit_publish_time")],
            [InlineKeyboardButton(BUTTON_BACK_TO_START, callback_data="back_to_start")]
        ]

        msg = await context.bot.send_message(
            chat_id=user_id,
            text=SETTINGS_TITLE,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

    async def update_audio_menu_after_edit(self, context, user_id):
        session = self.user_sessions[user_id]
        main_menu_message_id = session.get('main_menu_message_id')

        if main_menu_message_id:
            keyboard = [
                [InlineKeyboardButton(
                    BUTTON_AUTHOR.format(
                        session['current_artist'][:20] + "..." if len(session['current_artist']) > 20 else session[
                            'current_artist']),
                    callback_data="edit_author"
                )],
                [InlineKeyboardButton(
                    BUTTON_TITLE.format(
                        session['current_title'][:20] + "..." if len(session['current_title']) > 20 else session[
                            'current_title']),
                    callback_data="edit_title"
                )],
                [InlineKeyboardButton(
                    BUTTON_BPM.format(session['current_bpm']),
                    callback_data="edit_bpm"
                )],
                [InlineKeyboardButton(
                    BUTTON_TYPE.format(session['current_type'] or DEFAULT_TYPE_NAME),
                    callback_data="select_type"
                )],
                [InlineKeyboardButton(BUTTON_CREATE_VIDEO, callback_data="create_video")],
                [InlineKeyboardButton(BUTTON_CANCEL, callback_data="cancel_audio")]
            ]

            try:
                await context.bot.edit_message_caption(
                    chat_id=user_id,
                    message_id=main_menu_message_id,
                    caption=AUDIO_PROCESSED_TEXT,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

    async def send_temp_message(self, context, user_id, text, duration=3):
        msg = await context.bot.send_message(chat_id=user_id, text=text)
        await asyncio.sleep(duration)
        try:
            await msg.delete()
        except:
            pass

    async def create_video(self, query, context, user_id):
        session = self.user_sessions[user_id]

        processing_msg = await query.edit_message_caption(caption=VIDEO_CREATING)
        session['processing_message_id'] = processing_msg.message_id

        try:
            output_path = f"{session['user_dir']}/video.mp4"
            preview_path = f"{session['user_dir']}/preview.mp4"

            await asyncio.get_event_loop().run_in_executor(
                None,
                create_audio_visualizer,
                session['audio_path'],
                session['cover_path'],
                output_path,
                session['current_bpm']
            )

            await asyncio.get_event_loop().run_in_executor(
                None,
                self.create_preview_video,
                output_path,
                preview_path
            )

            session['video_path'] = output_path
            session['preview_path'] = preview_path

            description = self.generate_youtube_description(session, user_id)
            session['youtube_description'] = description

            # Получаем время публикации пользователя
            user_publish_time = self.db.get_scheduled_publish_time(user_id) or DEFAULT_PUBLISH_TIME
            publish_datetime_iso, scheduled_date = self.convert_msk_to_utc_iso(user_publish_time, user_id)
            session['publish_datetime_iso'] = publish_datetime_iso
            session['scheduled_date'] = scheduled_date

            video_info = VIDEO_CREATED_SCHEDULED.format(
                session['current_artist'],
                session['current_title'],
                session['current_bpm'],
                session['current_type'] or DEFAULT_TYPE_NAME,
                scheduled_date,
                user_publish_time
            )

            keyboard = [
                [InlineKeyboardButton(BUTTON_UPLOAD_YOUTUBE, callback_data="upload_youtube")],
                [InlineKeyboardButton(BUTTON_RECREATE, callback_data="recreate_video")],
                [InlineKeyboardButton(BUTTON_CANCEL, callback_data="back_to_audio")]
            ]

            try:
                await context.bot.delete_message(
                    chat_id=user_id,
                    message_id=session['processing_message_id']
                )
            except:
                pass

            with open(preview_path, 'rb') as video:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=video,
                    caption=video_info + PREVIEW_NOTE,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )

        except Exception as e:
            logger.error(f"Ошибка создания видео: {e}")
            await processing_msg.edit_caption(caption=ERROR_CREATING_VIDEO)

        return MAIN_MENU

    async def upload_to_youtube(self, query, context, user_id):
        session = self.user_sessions[user_id]
        await query.edit_message_caption(caption=UPLOADING_YOUTUBE)

        try:
            video_path = session['video_path']
            title = self.generate_youtube_title(session)
            description = session['youtube_description']
            thumbnail_path = session['video_path'].replace('.mp4', '_thumbnail.jpg')
            publish_datetime_iso = session['publish_datetime_iso']

            video_url = await asyncio.get_event_loop().run_in_executor(
                None,
                upload_to_youtube_scheduled,
                video_path, title, description, self.youtube_credentials, thumbnail_path,
                session['current_bpm'], session['current_artist'], publish_datetime_iso
            )

            user_publish_time = self.db.get_scheduled_publish_time(user_id) or DEFAULT_PUBLISH_TIME
            scheduled_date = session['scheduled_date']
            success_text = YOUTUBE_SUCCESS_SCHEDULED.format(
                video_url,
                session['current_artist'],
                session['current_title'],
                scheduled_date,
                user_publish_time
            )

            await query.edit_message_caption(caption=success_text)
            self.cleanup_session(user_id)

        except Exception as e:
            logger.error(f"Ошибка загрузки на YouTube: {e}")
            await query.edit_message_caption(caption=ERROR_UPLOADING_YOUTUBE)

        return MAIN_MENU

    def generate_youtube_description(self, session, user_id):
        description_parts = []
        description_parts.append(f"{session['current_bpm']} BPM")
        description_parts.append(f"")
        description_parts.append(f"τειεgrαm : @synworks")
        # Новая логика: парсим коллабораторов из тега автора
        collaborators = self.parse_collaborators_from_author_tag(session['current_artist'], user_id)

        if collaborators:
            user_beatmakers = self.db.get_user_beatmakers(user_id)
            beatmaker_dict = {bm['name'].lower(): bm['tag'] for bm in user_beatmakers}

            beatmaker_tags = []
            for collaborator in collaborators:
                tag = beatmaker_dict.get(collaborator.lower())
                if tag:
                    beatmaker_tags.append(tag)

            if beatmaker_tags:
                description_parts.append(f"")
                description_parts.append(f"w/ {', '.join(beatmaker_tags)}")

        current_type = session.get('current_type')
        if current_type:
            type_data = self.db.get_user_type_data(user_id, current_type)
            if type_data and type_data.get('tags'):
                description_parts.append(f"")
                description_parts.append(f"ταgs")
                description_parts.append(f"{type_data['tags']}")

        description_parts.append(f"")
        description_parts.append(f"#music #visualizer #syntunes")

        return '\n'.join(description_parts)

    def generate_youtube_title(self, session):
        title_parts = [session['current_artist']]
        title_parts.append('-')
        title_parts.append(session['current_title'])

        current_type = session.get('current_type')
        if current_type:
            title_parts.extend(['free', 'non', 'profit', current_type, 'type', 'beat'])

        return ' '.join(title_parts)

    async def cleanup_user_messages(self, user_id, context):
        session = self.user_sessions.get(user_id)
        if session and 'main_menu_message_id' in session:
            try:
                await context.bot.delete_message(
                    chat_id=user_id,
                    message_id=session['main_menu_message_id']
                )
            except:
                pass

    def cleanup_session(self, user_id):
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            user_dir = session.get('user_dir')
            if user_dir and os.path.exists(user_dir):
                import shutil
                shutil.rmtree(user_dir, ignore_errors=True)
            del self.user_sessions[user_id]

    def run(self):
        app = Application.builder().token(self.token).build()

        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                MessageHandler(filters.AUDIO, self.handle_audio)
            ],
            states={
                START_MENU: [
                    CallbackQueryHandler(self.handle_start_callback),
                    MessageHandler(filters.AUDIO, self.handle_audio)
                ],
                MAIN_MENU: [CallbackQueryHandler(self.handle_audio_callback)],
                EDIT_AUTHOR: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input),
                    CallbackQueryHandler(self.handle_audio_callback)
                ],
                EDIT_TITLE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input),
                    CallbackQueryHandler(self.handle_audio_callback)
                ],
                EDIT_BPM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input),
                    CallbackQueryHandler(self.handle_audio_callback)
                ],
                EDIT_PUBLISH_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input),
                    CallbackQueryHandler(self.handle_settings_callback)
                ],
                SETTINGS_MENU: [
                    CallbackQueryHandler(self.handle_settings_callback),
                    MessageHandler(filters.AUDIO, self.handle_audio)
                ],
                TYPES_SETTINGS: [
                    CallbackQueryHandler(self.handle_settings_callback),
                    MessageHandler(filters.AUDIO, self.handle_audio)
                ],
                BEATMAKERS_SETTINGS: [
                    CallbackQueryHandler(self.handle_settings_callback),
                    MessageHandler(filters.AUDIO, self.handle_audio)
                ],
                ADD_TYPE_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input),
                    CallbackQueryHandler(self.handle_settings_callback)
                ],
                ADD_TYPE_TAGS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input),
                    CallbackQueryHandler(self.handle_settings_callback)
                ],
                ADD_BEATMAKER_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input),
                    CallbackQueryHandler(self.handle_settings_callback)
                ],
                ADD_BEATMAKER_TAG: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input),
                    CallbackQueryHandler(self.handle_settings_callback)
                ],
            },
            fallbacks=[
                CommandHandler("start", self.start),
                MessageHandler(filters.AUDIO, self.handle_audio)
            ],
            per_user=True
        )

        app.add_handler(conv_handler)

        print("🤖 SynTunes Bot запущен!")
        app.run_polling()


def main():
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    YOUTUBE_CREDENTIALS = os.getenv("YOUTUBE_CREDENTIALS_PATH", "client_secrets.json")

    if not BOT_TOKEN:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не найден в .env файле!")
        return

    if not os.path.exists(YOUTUBE_CREDENTIALS):
        print(f"❌ Ошибка: Файл {YOUTUBE_CREDENTIALS} не найден!")
        return

    bot = SyntunesBot(BOT_TOKEN, YOUTUBE_CREDENTIALS)
    bot.run()


if __name__ == "__main__":
    main()
