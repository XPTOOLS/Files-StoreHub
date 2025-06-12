import asyncio
from pyrogram import filters
from pyrogram.types import Message

def register_reindex_command(bot, db, CONFIG, save_message_to_db):
    @bot.on_message(filters.command("reindex") & filters.user(CONFIG['ADMIN_IDS']))
    async def reindex_files(client, message: Message):
        await message.reply("🔄 Re-indexing files, please wait...")
        cursor = db['channel_files'].find()
        count = 0
        for file in cursor:
            msg_id = file['message_id']
            chat_id = file['chat_id']
            try:
                msg = await client.get_messages(chat_id, msg_id)
                await save_message_to_db(msg)
                count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Failed to reindex message {msg_id}: {e}")
                continue
        await message.reply(f"✅ Re-indexed {count} files.")
