from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

def register_tagstats_command(bot, db, CONFIG):
    @bot.on_message(filters.command("tagstats") & filters.user(CONFIG['ADMIN_IDS']))
    async def tag_statistics(client, message: Message):
        tag_stats = db['channel_files'].aggregate([
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ])
        
        result = "🏷️ <b>Top 10 Tags</b>\n\n"
        for tag in tag_stats:
            result += f"• #{tag['_id']}: {tag['count']} files\n"
        
        await message.reply(result, parse_mode=ParseMode.HTML)
