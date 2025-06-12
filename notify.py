# notify.py
import logging
import io
from datetime import datetime

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

NOTIFICATION_CHANNEL = "@smmserviceslogs"  # Replace with your actual channel


async def get_profile_photo(bot, user_id):
    """Download and process profile photo"""
    try:
        user = await bot.get_users(user_id)
        # get_chat_photos returns an async generator, so use async for
        photos = []
        async for photo in bot.get_chat_photos(user.id, limit=1):
            photos.append(photo)
        if not photos:
            raise Exception("No profile photo available")
        photo_file = await bot.download_media(photos[0].file_id)
        original_img = Image.open(photo_file).convert("RGB")
        # Create circular mask
        size = (500, 500)
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size[0], size[1]), fill=255)
        # Resize and apply mask
        img = ImageOps.fit(original_img, size, method=Image.LANCZOS)
        img.putalpha(mask)
        return img
    except Exception as e:
        logger.warning(f"Using default profile photo: {e}")
        # Create default gray circle (500x500)
        img = Image.new("RGBA", (500, 500), (70, 70, 70, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse((0, 0, 500, 500), fill=(100, 100, 100, 255))
        return img

async def generate_notification_image(bot, user_img, user_name, bot_name, action):
    """Generate a pro-quality notification image."""
    try:
        bot_user = await bot.get_me()
        bot_img = await get_profile_photo(bot, bot_user.id)
        # Create base image with rich gradient background
        width, height = 800, 400
        bg = Image.new("RGB", (width, height), (30, 30, 45))
        gradient = Image.new("L", (1, height), color=0xFF)
        for y in range(height):
            gradient.putpixel((0, y), int(255 * (1 - y/height)))
        alpha_gradient = gradient.resize((width, height))
        black_img = Image.new("RGB", (width, height), color=(10, 10, 25))
        bg = Image.composite(bg, black_img, alpha_gradient)
        draw = ImageDraw.Draw(bg)
        # Fonts - added fallback for each font individually
        try:
            title_font = ImageFont.truetype("arialbd.ttf", 40)
        except:
            title_font = ImageFont.load_default()
        try:
            name_font = ImageFont.truetype("arialbd.ttf", 28)
        except:
            name_font = ImageFont.load_default()
        try:
            action_font = ImageFont.truetype("arialbd.ttf", 24)
        except:
            action_font = ImageFont.load_default()
        # Draw top title
        draw.text((width // 2, 40), "NEW USER ACTIVITY", font=title_font,
                  fill="white", anchor="mm")
        # Helper to draw glowing circular image
        def draw_glowing_circle(base, img, pos, size, glow_color=(255, 215, 0)):
            glow = Image.new("RGBA", (size + 40, size + 40), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow)
            center = (glow.size[0] // 2, glow.size[1] // 2)
            for radius in range(size // 2 + 10, size // 2 + 20):
                glow_draw.ellipse([
                    center[0] - radius, center[1] - radius,
                    center[0] + radius, center[1] + radius
                ], fill=glow_color + (10,), outline=None)
            glow = glow.filter(ImageFilter.GaussianBlur(8))
            base.paste(glow, (pos[0] - 20, pos[1] - 20), glow)
            # Golden ring
            ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            ring_draw = ImageDraw.Draw(ring)
            ring_draw.ellipse((0, 0, size - 1, size - 1), outline=(255, 215, 0), width=6)
            # Add mask to image (ensure we're working with RGBA)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img = img.resize((size, size))
            mask = Image.new('L', (size, size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)
            base.paste(img, pos, img)
            base.paste(ring, pos, ring)
        # Paste profile images
        user_pos = (130, 120)
        bot_pos = (520, 120)
        draw_glowing_circle(bg, user_img, user_pos, 150)
        draw_glowing_circle(bg, bot_img, bot_pos, 150)
        # Draw usernames (with text length safety)
        max_name_length = 15
        safe_user_name = (user_name[:max_name_length] + '..') if len(user_name) > max_name_length else user_name
        safe_bot_name = (bot_name[:max_name_length] + '..') if len(bot_name) > max_name_length else bot_name
        draw.text((user_pos[0] + 75, 290), safe_user_name, font=name_font,
                  fill="white", anchor="ma")
        draw.text((bot_pos[0] + 75, 290), safe_bot_name, font=name_font,
                  fill="white", anchor="ma")
        # Draw action in the middle (with safety check)
        max_action_length = 30
        safe_action = (action[:max_action_length] + '..') if len(action) > max_action_length else action
        draw.text((width // 2, 330), f"Action: {safe_action}", font=action_font,
                  fill=(255, 215, 0), anchor="ma")
        # Bottom banner
        draw.rectangle([0, 370, width, 400], fill=(255, 215, 0))
        draw.text((width // 2, 385), "Powered by Files StoreHub", font=name_font,
                  fill=(30, 30, 30), anchor="mm")
        # Save to bytes
        img_byte_arr = io.BytesIO()
        bg.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr
    except Exception as e:
        logger.warning(f"Image generation error: {e}")
        return None

async def send_notification(bot, user_id, username, action, phone=None, amount=None):
    """Send notification to channel with generated image and styled caption"""
    try:
        user_img = await get_profile_photo(bot, user_id)
        bot_info = await bot.get_me()
        image_bytes = await generate_notification_image(bot, user_img, username, bot_info.first_name, action)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 Vɪꜱɪᴛ Bᴏᴛ", url=f"https://t.me/{bot_info.username}")]
        ])
        caption = f"""⭐️ ｢Uꜱᴇʀ Aᴄᴛɪᴠɪᴛʏ Nᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ 」⭐️
━━━━━━━━•❅•°•❈•°•❅•━━━━━━━━
➠ 🕵🏻‍♂️ Uꜱᴇʀɴᴀᴍᴇ: @{username or 'Not set'}
━━━━━━━━━━━━━━━━━━━━━━━
➠ 🆔 Uꜱᴇʀ Iᴅ: {user_id}
━━━━━━━━━━━━━━━━━━━━━━━
➠ 📦 Aᴄᴛɪᴏɴ: {action}"""
        if phone and amount:
            caption += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n➠ 📱 Pʜᴏɴᴇ: <code>{phone}</code>\n➠ 💸 Aᴍᴏᴜɴᴛ: <b>{amount:,} UGX</b>"
        caption += f"""
━━━━━━━━━━━━━━━━━━━━━━━
➠ ⏰ Tɪᴍᴇ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━
➠ 🤖 <b>Bᴏᴛ:</b> @{bot_info.username}
━━━━━━━━•❅•°•❈•°•❅•━━━━━━━━"""
        if image_bytes:
            await bot.send_photo(
                chat_id=NOTIFICATION_CHANNEL,
                photo=image_bytes,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
    except Exception as e:
        logger.warning(f"Error sending notification: {str(e)}")
