import asyncio
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

def register_broadcast_command(bot, db, CONFIG):
    @bot.on_message(filters.command("broadcast") & filters.user(CONFIG['ADMIN_IDS']))
    async def broadcast_command(client, message: Message):
        if len(message.command) < 2:
            await message.reply(
                "Usage: /broadcast <message>\n\n"
                "Example: /broadcast Hello everyone! This is an important update.",
                parse_mode=ParseMode.HTML
            )
            return
        
        broadcast_msg = message.text.split(' ', 1)[1]
        processing_msg = await message.reply("📡 Broadcasting message to users...")

        try:
            # Collect all unique user IDs
            files_collection = db['channel_files']
            users_collection = db['users']

            user_chats = files_collection.distinct("chat_id")
            start_users = users_collection.distinct("user_id")
            all_chats = list(set(user_chats + start_users))

            total_users = len(all_chats)
            success_count = 0
            failed_count = 0

            await processing_msg.edit_text(f"📡 Broadcasting to {total_users} users...")

            for chat_id in all_chats:
                try:
                    await client.send_message(
                        chat_id=chat_id,
                        text=broadcast_msg,
                        parse_mode=ParseMode.HTML
                    )
                    success_count += 1
                    await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"Failed to send to {chat_id}: {e}")
                    failed_count += 1

            report_msg = (
                "📊 <b>Broadcast Report</b>\n\n"
                f"✅ Successfully sent to: {success_count} users\n"
                f"❌ Failed to send to: {failed_count} users\n"
                f"📩 Total attempted: {total_users} users"
            )
            await processing_msg.edit_text(report_msg, parse_mode=ParseMode.HTML)

        except Exception as e:
            await processing_msg.edit_text(f"❌ Error during broadcast: {e}")
            print(f"Broadcast error: {e}")
