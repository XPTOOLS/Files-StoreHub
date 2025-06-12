from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

def register_fileinfo_command(bot, db, CONFIG):
    @bot.on_message(filters.command("fileinfo") & filters.user(CONFIG['ADMIN_IDS']))
    async def file_info(client, message: Message):
        if len(message.command) < 2:
            await message.reply("Usage: /fileinfo <message_id>")
            return
        
        msg_id = int(message.command[1])
        file = db['channel_files'].find_one({"message_id": msg_id})
        
        if not file:
            await message.reply("❌ File not found.")
            return
        
        tags = " ".join(f"#{t}" for t in file.get('tags', []))
        title = file.get('title', 'Unknown')
        ftype = file.get('file_type', 'N/A')
        date = file.get('date')
        
        text = (
            "📄 <b>File Info</b>\n\n"
            f"🆔 <b>ID:</b> <code>{msg_id}</code>\n"
            f"📂 <b>Type:</b> {ftype}\n"
            f"📎 <b>Title:</b> {title}\n"
            f"🏷️ <b>Tags:</b> {tags or 'None'}\n"
            f"🕒 <b>Date:</b> {date}"
        )
        await message.reply(text, parse_mode=ParseMode.HTML)
