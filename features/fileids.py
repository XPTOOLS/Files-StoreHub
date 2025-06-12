from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

def register_fileids_command(bot, db, CONFIG):
    @bot.on_message(filters.command("fileids") & filters.user(CONFIG['ADMIN_IDS']))
    async def list_file_ids(client, message: Message):
        files = db['channel_files'].find().sort("date", -1).limit(20)
        if not files:
            await message.reply("No files found.")
            return
        
        text = "📄 <b>Recent Files</b>\n\n"
        for f in files:
            text += f"• <b>{f.get('title', 'Untitled')}</b> — ID: <code>{f['message_id']}</code>\n"
        
        await message.reply(text, parse_mode=ParseMode.HTML)
