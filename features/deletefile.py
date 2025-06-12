from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# In-memory store for pending deletions
pending_bulk_deletions = {}

def register_deletefile_commands(bot, db, CONFIG):
    
    @bot.on_message(filters.command("deletefile") & filters.user(CONFIG['ADMIN_IDS']))
    async def start_bulk_deletion(client, message: Message):
        pending_bulk_deletions[message.from_user.id] = []
        await message.reply(
            "✅ Now forward the files you want to delete from the channel.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Done", callback_data="finish_bulk_deletion")]
            ])
        )

    @bot.on_message(filters.forwarded & filters.user(CONFIG['ADMIN_IDS']))
    async def collect_forwarded_files(client, message: Message):
        user_id = message.from_user.id

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

    @bot.on_callback_query(filters.regex("finish_bulk_deletion") & filters.user(CONFIG['ADMIN_IDS']))
    async def complete_bulk_deletion(client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        to_delete = pending_bulk_deletions.pop(user_id, [])

        print(f"[DEBUG] Deletion triggered by user: {user_id}")
        print(f"[DEBUG] Files queued for deletion: {to_delete}")

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
            "You can now start a new bulk deletion if needed.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Start New Deletion", callback_data="start_bulk_deletion")]
            ])
        )