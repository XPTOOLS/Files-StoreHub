from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

def register_stats_command(bot, db, CONFIG):
    @bot.on_message(filters.command("stats") & filters.user(CONFIG['ADMIN_IDS']))
    async def stats_command(client, message: Message):
        try:
            # Collections
            users_collection = db['users']
            files_collection = db['channel_files']
            
            # User and file counts
            total_users = users_collection.count_documents({})
            total_files = files_collection.count_documents({})
            
            # File type stats
            file_types = files_collection.aggregate([
                {"$group": {"_id": "$file_type", "count": {"$sum": 1}}}
            ])
            file_type_stats = "\n".join([
                f"▫️ {doc['_id'] or 'unknown'}: {doc['count']}" 
                for doc in file_types
            ]) or "No file type data"
            
            # Tag stats
            tag_stats = files_collection.aggregate([
                {"$unwind": "$tags"},
                {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ])
            top_tags = "\n".join([
                f"▫️ #{doc['_id']}: {doc['count']}" 
                for doc in tag_stats
            ]) or "No tag data"
            
            # Active users (last 30 days)
            active_users = users_collection.count_documents({
                "last_interaction": {"$gt": datetime.now() - timedelta(days=30)}
            })
            
            # Database stats
            db_stats = db.command("dbstats")
            storage_size_mb = db_stats['storageSize'] / (1024 * 1024)
            data_size_mb = db_stats['dataSize'] / (1024 * 1024)
            
            # Compose reply
            stats_message = (
                "📊 <b>Bot Statistics</b>\n\n"
                f"👤 <b>Users:</b> {total_users}\n"
                f"▫️ Active (last 30 days): {active_users}\n\n"
                f"📂 <b>Files:</b> {total_files}\n"
                f"<b>File Types:</b>\n{file_type_stats}\n\n"
                f"🏷️ <b>Top 10 Tags:</b>\n{top_tags}\n\n"
                f"💾 <b>Database Storage:</b>\n"
                f"▫️ Data Size: {data_size_mb:.2f} MB\n"
                f"▫️ Storage Size: {storage_size_mb:.2f} MB"
            )
            
            await message.reply(stats_message, parse_mode=ParseMode.HTML)
        
        except Exception as e:
            await message.reply(f"❌ Error generating stats: {e}")
            print(f"Stats error: {e}")
