from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

def register_inactive_command(bot, db, CONFIG):
    @bot.on_message(filters.command("inactive") & filters.user(CONFIG['ADMIN_IDS']))
    async def inactive_users(client, message: Message):
        days = 30
        threshold = datetime.now() - timedelta(days=days)
        users_collection = db['users']
        
        inactive = users_collection.find({"last_interaction": {"$lt": threshold}})
        total = users_collection.count_documents({"last_interaction": {"$lt": threshold}})
        
        msg = f"📋 <b>Inactive Users (>{days} days)</b>\n\n"
        for user in inactive.limit(20):  # Show only top 20
            username = user.get("username")
            if username:
                msg += f"• @{username}\n"
            else:
                msg += f"• ID: <code>{user['user_id']}</code>\n"
        
        msg += f"\nTotal inactive: {total}"
        await message.reply(msg, parse_mode=ParseMode.HTML)
