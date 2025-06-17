import os
import re
import aiohttp
from aiohttp import web
import asyncio
import logging
from typing import List
from datetime import timedelta
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatMemberStatus
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    CallbackQuery,
    Message
)
from pyrogram.errors import BadRequest
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
from urllib.parse import unquote


# Import feature modules
from features.stats import register_stats_command
from features.broadcast import register_broadcast_command
from features.reindex import register_reindex_command
from features.deletefile import register_deletefile_commands
from features.inactive import register_inactive_command
from features.tagstats import register_tagstats_command
from features.fileinfo import register_fileinfo_command
from features.fileids import register_fileids_command

from notify import send_notification


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration from environment variables
CONFIG = {
    'API_ID': int(os.getenv('API_ID', '25753873')),
    'API_HASH': os.getenv('API_HASH', '3a5cdc2079cd76af80586102bd9761e2'),
    'BOT_TOKEN': os.getenv('BOT_TOKEN', '8070267972:AAFOlNRDCXMPo1M7OALyEmSPdbFHwVXjVEk'),
    'SOURCE_CHANNEL': os.getenv('SOURCE_CHANNEL', '@Filesstoragee'),
    'ADMIN_IDS': [int(i.strip()) for i in os.getenv('ADMIN_IDS', '5962658076').split(',') if i.strip().isdigit()],
    'WELCOME_IMAGE': "https://envs.sh/keh.jpg",
    'MONGO_URI': os.getenv('MONGO_URI', 'mongodb+srv://anonymousguywas:12345Trials@cluster0.t4nmrtp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'),
    'DB_NAME': os.getenv('DB_NAME', 'telegramstore')
}

# Force Join Configuration
CHANNEL_USERNAMES = [name.strip() for name in os.getenv("CHANNEL_USERNAMES", "@megahubbots").split(",")]
CHANNEL_LINKS = [link.strip() for link in os.getenv("CHANNEL_LINKS", "https://t.me/megahubbots").split(",")]

# Ensure all channel usernames start with @
CHANNEL_USERNAMES = [name if name.startswith("@") else f"@{name}" for name in CHANNEL_USERNAMES]

if len(CHANNEL_USERNAMES) != len(CHANNEL_LINKS):
    logger.error("CHANNEL_USERNAMES and CHANNEL_LINKS must have the same number of elements")
    raise ValueError("Channel configuration mismatch")

# Initialize MongoDB
mongo_client = MongoClient(CONFIG['MONGO_URI'])
db = mongo_client[CONFIG['DB_NAME']]
files_collection = db['channel_files']
users_collection = db['users']

# Initialize bot
bot = Client(
    "content_bot",
    api_id=CONFIG['API_ID'],
    api_hash=CONFIG['API_HASH'],
    bot_token=CONFIG['BOT_TOKEN']
)

# Welcome image URL
WELCOME_IMAGE = CONFIG['WELCOME_IMAGE']

# Main menu - Simplified with only Help and About
def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ℹ️ About Us", callback_data="about"),
            InlineKeyboardButton("🆘 Help", callback_data="help")
        ],
        [
            InlineKeyboardButton("📄 Terms & Conditions", callback_data="terms"),
            InlineKeyboardButton("📞 Contact Us", callback_data="contact")
        ]
    ])

async def is_user_member(client: Client, user_id: int) -> bool:
    """Check if user is member of all required channels."""
    for channel in CHANNEL_USERNAMES:
        try:
            channel = channel.strip()
            if not channel.startswith("@"): channel = f"@{channel}"
            member = await client.get_chat_member(channel, user_id)
            # Use enum for status comparison
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                logger.info(f"User {user_id} not member of {channel} (status: {member.status})")
                return False
        except BadRequest as e:
            logger.error(f"Error checking membership for {channel}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking membership: {e}")
            return False
    return True

async def prompt_force_join(message: Message):
    """Send force join message with buttons for all channels."""
    buttons = []
    for i, channel in enumerate(CHANNEL_USERNAMES):
        display_name = channel.lstrip('@')
        buttons.append([
            InlineKeyboardButton(f"Join {display_name}", url=CHANNEL_LINKS[i])
        ])
    
    buttons.append([InlineKeyboardButton("✅ I've Joined", callback_data="verify_join")])
    
    await message.reply_text(
        "🔒 *Access Restricted* 🔒\n\n"
        "To use this bot, you must join our official channels:\n\n"
        "👉 Tap each button below to join\n"
        "👉 Then click 'I've Joined' to verify",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@bot.on_callback_query(filters.regex(r"^verify_join$"))
async def verify_join_callback(client: Client, callback_query: CallbackQuery):
    """Handle join verification callback"""
    user_id = callback_query.from_user.id
    logger.info(f"Verifying join for user {user_id}")
    
    is_member = await is_user_member(client, user_id)
    logger.info(f"Verification result for {user_id}: {is_member}")
    
    if is_member:
        await callback_query.answer("✅ Verification successful! You can now use the bot.")
        await callback_query.message.edit_text(
            "✅ *Verification Complete!*\n\n"
            "You've successfully joined all required channels.\n"
            "Use /start to begin!",
            parse_mode=ParseMode.HTML
        )
        # Update user status in DB
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'verified_member': True}},
            upsert=True
        )
    else:
        await callback_query.answer("❌ You haven't joined all channels yet!", show_alert=True)
        # Log which channels are missing
        for channel in CHANNEL_USERNAMES:
            try:
                member = await client.get_chat_member(channel, user_id)
                logger.info(f"User {user_id} status in {channel}: {member.status}")
            except Exception as e:
                logger.error(f"Error checking {channel}: {e}")

def clean_filename(filename):
    """Clean and format filename for display"""
    if not filename:
        return "Untitled"
    
    # Remove common extensions and special characters
    filename = re.sub(r'\.[^\.]+$', '', filename)  # Remove extension
    filename = re.sub(r'[_-]', ' ', filename)      # Replace underscores/hyphens with spaces
    filename = unquote(filename)                   # Decode URL-encoded characters
    return filename.strip().title()

def extract_metadata(message):
    """Extract metadata from message including filename and tags"""
    # Get filename from document or photo
    filename = ""
    if message.document:
        filename = message.document.file_name or ""
    elif message.photo:
        filename = f"photo_{message.photo.file_unique_id}.jpg"
    
    # Clean filename for display
    display_name = clean_filename(filename)
    
    # Extract tags from caption or filename
    tags = set()
    if message.caption:
        tags.update(re.findall(r"#(\w+)", message.caption.lower()))
    
    # Additional tags from filename (words with special meaning)
    filename_tags = {
        'mod': ['mod', 'modded', 'hack'],
        'file': ['file', 'config', 'settings']
    }
    
    for word in re.findall(r'\w+', filename.lower()):
        for tag, variants in filename_tags.items():
            if word in variants:
                tags.add(tag)
    
    # Extract country if mentioned in filename or caption
    countries = ['uganda', 'kenya', 'tanzania', 'south africa']
    for country in countries:
        if country in filename.lower() or (message.caption and country in message.caption.lower()):
            tags.add(country.replace(' ', '_'))
    
    return {
        'display_name': display_name,
        'tags': list(tags),
        'filename': filename
    }

async def save_message_to_db(message):
    if not message.caption and not message.document and not message.photo and not message.video:
        return
    
    metadata = extract_metadata(message)
    clean_caption = re.sub(r'Forwarded from .+\n', '', message.caption or "").strip()
    
    file_data = {
        'message_id': message.id,
        'chat_id': message.chat.id,
        'date': message.date,
        'saved_at': datetime.now(),
        'title': metadata['display_name'],
        'tags': metadata['tags'],
        'filename': metadata['filename'],
        'file_type': None,
        'file_id': None,
        'caption': clean_caption
    }
    
    # Determine file type and ID
    if message.document:
        file_data['file_type'] = 'document'
        file_data['file_id'] = message.document.file_id
    elif message.photo:
        file_data['file_type'] = 'photo'
        file_data['file_id'] = message.photo.file_id
    elif message.video:
        file_data['file_type'] = 'video'
        file_data['file_id'] = message.video.file_id
    
    # Update or insert the document
    files_collection.update_one(
        {'message_id': message.id, 'chat_id': message.chat.id},
        {'$set': file_data},
        upsert=True
    )

def format_search_results(files, query, page=1, results_per_page=10):
    if not files:
        return "No results found for your search.", 0, 1
    
    total_results = len(files)
    start_idx = (page - 1) * results_per_page
    end_idx = start_idx + results_per_page
    paginated_files = files[start_idx:end_idx]
    
    message = f"🔍 <b>Search Results for '{query}'</b>\n\n"
    message += f"📂 <i>{total_results} items found</i>\n\n"
    
    for file in paginated_files:
        title = file.get('title', 'Untitled')
        message += f"▫️ <b>{title}</b>\n"
    
    message += "\nClick on an item to download it."
    return message, total_results, page

async def search_files(query):
    # Normalize the query and extract search terms
    query = query.lower().strip()
    search_terms = re.sub(r'#\w+', '', query).strip()
    query_keywords = set(re.findall(r'#(\w+)', query))
    
    # Build search query
    search_query = {}
    
    # If we have specific keywords, search for files that match ALL of them
    if query_keywords:
        search_query['tags'] = {'$all': list(query_keywords)}
    
    # If we have search terms, search in title, filename, and caption
    if search_terms:
        regex = re.compile(re.escape(search_terms), re.IGNORECASE)
        text_search = {
            '$or': [
                {'title': regex},
                {'filename': regex},
                {'caption': regex}
            ]
        }
        
        if search_query:
            search_query = {'$and': [search_query, text_search]}
        else:
            search_query = text_search
    
    return list(files_collection.find(search_query).sort('date', -1))

async def send_files_to_user(client, chat_id, files):
    sent_messages = []

    for file in files:
        caption = file.get('caption', '')
        try:
            if file['file_type'] == 'photo':
                msg = await client.send_photo(
                    chat_id, 
                    file['file_id'], 
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
            elif file['file_type'] == 'document':
                msg = await client.send_document(
                    chat_id, 
                    file['file_id'], 
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
            elif file['file_type'] == 'video':
                msg = await client.send_video(
                    chat_id, 
                    file['file_id'], 
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
            sent_messages.append(msg)
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error sending file: {e}")

    warning_text = (
        "<blockquote>"
        "<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\n"
        "This Files/Videos will be deleted in <b><u>10 mins</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n"
        "<b><i>Please forward this ALL Files/Videos to your Saved Messages and Start Download there</i></b>"
        "</blockquote>"
    )

    if sent_messages:
        warning_msg = await sent_messages[-1].reply(
            warning_text,
            parse_mode=ParseMode.HTML,
            quote=True
        )
    else:
        warning_msg = await client.send_message(
            chat_id,
            warning_text,
            parse_mode=ParseMode.HTML
        )

    async def delete_after_delay(messages):
        await asyncio.sleep(600)  # 10 minutes delay
        for msg in messages:
            try:
                await msg.delete()
            except Exception as e:
                logger.error(f"Error deleting message: {e}")
        try:
            await warning_msg.edit_text(
                "🗑️ <i>Files have been automatically deleted</i>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error editing warning message: {e}")

    asyncio.create_task(delete_after_delay(sent_messages))

@bot.on_message(
    filters.text
    & ~filters.command(["start", "help", "about", "broadcast", "stats", "reindex", 
                        "deletefile", "inactive", "tagstats", "fileinfo", "fileids"])
    & ~filters.chat(CONFIG['SOURCE_CHANNEL'])
)
async def search_handler(client, message: Message):
    if not await is_user_member(client, message.from_user.id):
        await prompt_force_join(message)
        return
    
    # Log the search query
    await send_notification(client, message.from_user.id, getattr(message.from_user, 'username', None), "Searched for files",)
    logger.info(f"User {message.from_user.id} searched for files: {message.text.strip()}")
    
    query = message.text.strip()
    if len(query) < 3:
        await message.reply("Please enter at least 3 characters to search.")
        return
    
    files = await search_files(query)
    if files:
        response, total_results, current_page = format_search_results(files, query)
        
        buttons = []
        start_idx = (current_page - 1) * 10
        end_idx = start_idx + 10
        for file in files[start_idx:end_idx]:
            title = file.get('title', 'Untitled')
            buttons.append([
                InlineKeyboardButton(
                    title[:30] + ("..." if len(title) > 30 else ""),
                    callback_data=f"file:{file['message_id']}"
                )
            ])
        
        pagination_buttons = []
        if current_page > 1:
            pagination_buttons.append(
                InlineKeyboardButton("⬅️ Previous", callback_data=f"search_page:{query}:{current_page-1}")
            )
        if end_idx < total_results:
            pagination_buttons.append(
                InlineKeyboardButton("Next ➡️", callback_data=f"search_page:{query}:{current_page+1}")
            )
        
        if pagination_buttons:
            buttons.append(pagination_buttons)
        
        buttons.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="go_back:main")])
        
        await message.reply(
            response,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
    else:
        await message.reply(f"No results found for '{query}'")

@bot.on_callback_query(filters.regex(r"^file:"))
async def file_result_handler(client, callback_query: CallbackQuery):
    message_id = int(callback_query.data.split(":")[1])
    file = files_collection.find_one({"message_id": message_id})
    
    if file:
        await callback_query.answer()
        await send_files_to_user(client, callback_query.message.chat.id, [file])
    else:
        await callback_query.answer("File no longer available", show_alert=True)

@bot.on_callback_query(filters.regex(r"^search_page:"))
async def search_page_handler(client, callback_query: CallbackQuery):
    data = callback_query.data.split(":")
    query = data[1]
    page = int(data[2])
    
    files = await search_files(query)
    if files:
        response, total_results, _ = format_search_results(files, query, page)
        
        buttons = []
        start_idx = (page - 1) * 10
        end_idx = start_idx + 10
        for file in files[start_idx:end_idx]:
            title = file.get('title', 'Untitled')
            buttons.append([
                InlineKeyboardButton(
                    title[:30] + ("..." if len(title) > 30 else ""),
                    callback_data=f"file:{file['message_id']}"
                )
            ])
        
        pagination_buttons = []
        if page > 1:
            pagination_buttons.append(
                InlineKeyboardButton("⬅️ Previous", callback_data=f"search_page:{query}:{page-1}")
            )
        if end_idx < total_results:
            pagination_buttons.append(
                InlineKeyboardButton("Next ➡️", callback_data=f"search_page:{query}:{page+1}")
            )
        
        if pagination_buttons:
            buttons.append(pagination_buttons)
        
        buttons.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="go_back:main")])
        
        await callback_query.message.edit_text(
            response,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
    else:
        await callback_query.answer("No results found", show_alert=True)

@bot.on_message(filters.chat(CONFIG['SOURCE_CHANNEL']))
async def channel_message_handler(client, message: Message):
    if message.edit_date:
        return
    await save_message_to_db(message)

@bot.on_message(filters.command("start"))
async def start_handler(client, message: Message):
    if not await is_user_member(client, message.from_user.id):
        await prompt_force_join(message)
        return
    
    await send_notification(client, message.from_user.id, getattr(message.from_user, 'username', None), "Started the bot")
    logger.info(f"User {message.from_user.id} started the bot")
    
    # Store user info in database
    users_collection.update_one(
        {'user_id': message.from_user.id},
        {'$set': {
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name,
            'last_interaction': datetime.now()
        }},
        upsert=True
    )
    
    await message.reply_photo(
        photo=WELCOME_IMAGE,
        caption="✨ <b>Welcome to Content Provider Bot!</b>\n\nSearch for any file you need:",
        reply_markup=main_menu(),
        parse_mode=ParseMode.HTML
    )

# [Rest of your existing handlers...]
@bot.on_message(filters.command("help"))
async def help_command(client, message: Message):
    await message.reply(
        "🆘 <b>Help</b>\n\nHow to use this bot:\n"
        "1. Search for what you need (e.g., 'Airtel Uganda #file')\n"
        "2. Click on the result\n"
        "3. Download the file\n\n"
        "You can use multiple keywords like:\n"
        "- #mod #freenethubz\n"
        "- #file #uganda\n"
        "- #mod #game\n"
        "Or search by filename parts",
        parse_mode=ParseMode.HTML
    )

@bot.on_message(filters.command("about"))
async def about_command(client, message: Message):
    await message.reply(
        "ℹ️ <b>About Us</b>\n\nThis bot provides various files and apps.\n\nCreated with ❤️ for our users.",
        parse_mode=ParseMode.HTML
    )

# Temporary memory for admins in delete mode
# Track pending deletions per admin
pending_bulk_deletions = {}  # user_id: list of (chat_id, message_id)


# Step 1: Initiate deletion mode
@bot.on_message(filters.command("deletefile") & filters.user(CONFIG['ADMIN_IDS']))
async def start_bulk_deletion(client, message):
    pending_bulk_deletions[message.from_user.id] = []
    await message.reply(
        "✅ Now forward the files you want to delete from the channel.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Done", callback_data="finish_bulk_deletion")]
        ])
    )

@bot.on_message(filters.forwarded & filters.user(CONFIG['ADMIN_IDS']))
async def collect_forwarded_files(client, message):
    user_id = message.from_user.id

    # Check if user is in delete mode
    if user_id not in pending_bulk_deletions:
        return

    if not message.forward_from_chat or not message.forward_from_message_id:
        await message.reply("❌ Please forward valid files directly from the source channel.")
        return

    pending_bulk_deletions[user_id].append((
        message.forward_from_chat.id,
        message.forward_from_message_id
    ))
    await message.reply("✅ File queued for deletion.")


# Step 2: Handle forwarded file
@bot.on_callback_query(filters.regex("finish_bulk_deletion") & filters.user(CONFIG['ADMIN_IDS']))
async def complete_bulk_deletion(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    to_delete = pending_bulk_deletions.pop(user_id, [])

    if not to_delete:
        await callback_query.answer("No files were queued.", show_alert=True)
        return
    
    await callback_query.message.edit_text(
            "🗑️ <b>Deleting files...</b>\n\n"
            "This may take a while depending on the number of files.",
            parse_mode=ParseMode.HTML
        )

    success_count = 0
    db_count = 0
    failed = 0

    for chat_id, msg_id in to_delete:
        try:
            await client.delete_messages(chat_id, msg_id)
            success_count += 1
        except Exception as e:
            print(f"Failed to delete from channel: {e}")
            failed += 1

        result = db['channel_files'].delete_one({
            'message_id': msg_id,
            'chat_id': chat_id
        })
        if result.deleted_count:
            db_count += 1

    await callback_query.message.edit_text(
        f"🗑️ <b>Bulk Deletion Complete</b>\n\n"
        f"✅ Deleted from Channel: {success_count}\n"
        f"🗃️ Deleted from Database: {db_count}\n"
        f"⚠️ Failed deletions: {failed}",
        parse_mode=ParseMode.HTML
    )
    await callback_query.answer("Deletion complete.")
    await callback_query.message.reply(
            "You can now start a new bulk deletion if needed. Just type /deletefile to begin.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Start New Deletion", callback_data="/deletefile")]
            ])
        )

@bot.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    data = callback_query.data

    if data == "about":
        await callback_query.message.edit_caption(
            caption="ℹ️ <b>About Us</b>\n\nThis bot provides various files and apps.\n\nCreated with ❤️ for our users.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="go_back:main")]
            ])
        )
        await callback_query.answer()

    elif data == "help":
        await callback_query.message.edit_caption(
            caption=(
                "🆘 <b>Help</b>\n\n"
                "How to use this bot:\n"
                "1. Search for what you need (e.g., 'Airtel Uganda #file')\n"
                "2. Click on the result\n"
                "3. Download the file\n\n"
                "You can use multiple keywords like:\n"
                "- #mod #freenethubz\n"
                "- #file #uganda\n"
                "- #mod #game\n"
                "Or search by filename parts"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="go_back:main")]
            ])
        )
        await callback_query.answer()

    elif data == "terms":
        await callback_query.message.edit_caption(
            caption=(
                "📄 <b>Terms & Conditions</b>\n\n"
                "By using this bot, you agree to the following:\n"
                "- Do not misuse the service\n"
                "- Respect copyright laws\n"
                "- Admins may remove access at any time\n"
                "- You are responsible for what you download\n\n"
                "Please read carefully and accept the terms to continue."
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ I Accept T&C", callback_data="accept_terms")],
                [InlineKeyboardButton("⬅️ Back", callback_data="go_back:main")]
            ])
        )
        await callback_query.answer()

    elif data == "accept_terms":
        await callback_query.message.edit_caption(
            caption="✅ You have accepted the Terms & Conditions.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Main", callback_data="go_back:main")]
            ])
        )
        await callback_query.answer("Thank you for accepting.")

    elif data == "contact":
        await callback_query.message.edit_caption(
            caption=(
                "📞 <b>Contact Us</b>\n\n"
                "For support or inquiries, feel free to reach out to us through the provided buttons.\n\n"
                "We value your feedback and are here to assist you with any questions or issues you may have.\n\n"
                "We'll respond within 24 hours!"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👨‍💻 Contact Developer", url="https://t.me/AM_ITACHIUCHIHA")],
                [InlineKeyboardButton("📢 Bot Updates", url="https://t.me/Megahubbots")],
                [InlineKeyboardButton("⬅️ Back to Main", callback_data="go_back:main")]
            ])
        )
        await callback_query.answer()

    elif data.startswith("go_back:"):
        await callback_query.message.edit_media(
            media=InputMediaPhoto(
                CONFIG['WELCOME_IMAGE'],
                caption="✨ <b>Content Provider Bot</b>\n\nSearch for any file you need:",
                parse_mode=ParseMode.HTML
            ),
            reply_markup=main_menu()
        )
        await callback_query.answer()


def register_all_features():
    register_stats_command(bot, db, CONFIG)
    register_broadcast_command(bot, db, CONFIG)
    register_reindex_command(bot, db, CONFIG, save_message_to_db)
    register_deletefile_commands(bot, db, CONFIG)
    register_inactive_command(bot, db, CONFIG)
    register_tagstats_command(bot, db, CONFIG)
    register_fileinfo_command(bot, db, CONFIG)
    register_fileids_command(bot, db, CONFIG)

WEBHOOK_PATH = f"/{CONFIG['BOT_TOKEN']}"
PORT = int(os.environ.get("PORT", 10000))
RENDER_HOST = os.environ.get("https://files-storehub.onrender.com")

async def handle_webhook(request):
    data = await request.json()
    await bot.process_update(data)
    return web.Response(text="OK")

async def main():
    logger.info("Bot is starting...")
    register_all_features()
    
    if RENDER_HOST:
        WEBHOOK_URL = f"https://{RENDER_HOST}{WEBHOOK_PATH}"
        await bot.start()
        app = web.Application()
        app.router.add_post(WEBHOOK_PATH, handle_webhook)

        # Add a simple GET route at root
        async def index(request):
            return web.Response(
    text="<h2>✅ Telegram Bot is Running</h2><p>This server is for webhook only.</p>",
    content_type='text/html'
)

        app.router.add_get("/", index)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"Webhook running on {WEBHOOK_URL}")
        while True:
            await asyncio.sleep(3600)
    else:
        logger.info("Running in polling mode...")
        await bot.run()

if __name__ == '__main__':
    if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
        asyncio.run(main())
    else:
        register_all_features()
        bot.run()
