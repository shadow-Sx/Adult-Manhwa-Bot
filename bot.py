import os
import logging
from flask import Flask, request
from dotenv import load_dotenv
from telebot import types
import telebot
from database import db

# Environment variables yuklash
load_dotenv()

# Logger sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Bot token
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")

# Admin IDlar
ADMIN_IDS = os.getenv('ADMIN_IDS', '')
ADMIN_IDS = [int(id.strip()) for id in ADMIN_IDS.split(',') if id.strip()] if ADMIN_IDS else []

# Majburiy kanallar
CHANNELS = os.getenv('CHANNELS', '')
CHANNELS = [ch.strip() for ch in CHANNELS.split(',') if ch.strip()] if CHANNELS else []

# Bot yaratish
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# ==================== Yordamchi funksiyalar ====================

def is_admin(user_id):
    """Admin tekshirish"""
    return not ADMIN_IDS or user_id in ADMIN_IDS

def check_subscription(user_id):
    """Obuna tekshirish"""
    if not CHANNELS:
        return True, None
    
    not_subscribed = []
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked']:
                chat = bot.get_chat(channel)
                not_subscribed.append({
                    'title': chat.title,
                    'username': chat.username,
                    'id': channel
                })
        except Exception as e:
            logger.error(f"Kanal tekshirishda xato: {e}")
            continue
    
    return len(not_subscribed) == 0, not_subscribed

def get_subscription_keyboard(not_subscribed):
    """Obuna tugmalari"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for ch in not_subscribed:
        keyboard.add(types.InlineKeyboardButton(
            f"📢 {ch['title']}", 
            url=f"https://t.me/{ch['username']}"
        ))
    keyboard.add(types.InlineKeyboardButton(
        "✅ Obunani tekshirish", 
        callback_data="check_sub"
    ))
    return keyboard

def get_main_keyboard():
    """Asosiy menyu"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton("📚 Barcha manhwalar"),
        types.KeyboardButton("🔍 Qidirish"),
        types.KeyboardButton("🎭 Janrlar"),
        types.KeyboardButton("📊 Statistika"),
        types.KeyboardButton("ℹ️ Yordam")
    )
    if ADMIN_IDS:
        keyboard.add(types.KeyboardButton("⚙️ Admin panel"))
    return keyboard

def get_admin_keyboard():
    """Admin panel"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton("📤 Manhwa yuklash"),
        types.KeyboardButton("📋 Barcha manhwalar"),
        types.KeyboardButton("❌ Manhwa o'chirish"),
        types.KeyboardButton("📊 To'liq statistika"),
        types.KeyboardButton("📢 E'lon yuborish"),
        types.KeyboardButton("⬅️ Asosiy menyu")
    )
    return keyboard

def send_manhwa_file(chat_id, manhwa):
    """Manhwa faylini yuborish"""
    try:
        file_id = manhwa['file_id']
        media_type = manhwa.get('media_type', 'document')
        
        caption = f"""
📖 <b>{manhwa['title']}</b>
📑 Chapter: <b>{manhwa['chapter']}</b>
"""
        if manhwa.get('genre'):
            caption += f"🎭 Janr: {', '.join(manhwa['genre'])}\n"
        if manhwa.get('description'):
            caption += f"📝 {manhwa['description'][:200]}\n"
        
        if media_type == 'photo':
            bot.send_photo(chat_id, file_id, caption=caption)
        elif media_type == 'video':
            bot.send_video(chat_id, file_id, caption=caption)
        else:
            bot.send_document(chat_id, file_id, caption=caption)
        
        # Yuklab olish statistikasi
        db.increment_downloads(file_id)
        return True
    except Exception as e:
        logger.error(f"Fayl yuborishda xato: {e}")
        return False

# ==================== Bot komandalari ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    """Start komandasi"""
    user = message.from_user
    
    # Foydalanuvchini saqlash
    db.add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Obuna tekshirish
    is_subscribed, not_subscribed = check_subscription(user.id)
    
    if not is_subscribed:
        bot.send_message(
            message.chat.id,
            "👋 Assalomu alaykum! Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=get_subscription_keyboard(not_subscribed)
        )
        return
    
    welcome_text = f"""
👋 Assalomu alaykum, {user.first_name}!

📚 <b>Manhwa bot</b>ga xush kelibsiz!

Bu bot orqali siz:
• 📖 Koreys komikslarini yuklab olishingiz
• 🔍 Janr va nom bo'yicha qidirishingiz
• 📊 Yuklab olishlar statistikasini ko'rishingiz mumkin

Quyidagi menyudan kerakli bo'limni tanlang 👇
"""
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard())

@bot.message_handler(commands=['help'])
def help_command(message):
    """Yordam komandasi"""
    help_text = """
📖 <b>Yordam</b>

<b>Mavjud komandalar:</b>
/start - Botni qayta ishga tushirish
/help - Yordam
/search <i>nomi</i> - Manhwa qidirish
/genres - Janrlar ro'yxati

<b>Admin komandalari:</b>
/upload - Yangi manhwa yuklash
/stats - Batafsil statistika
/broadcast - E'lon yuborish

📝 <b>Qanday foydalanish:</b>
1. Menyudan kerakli bo'limni tanlang
2. Manhwa nomi yoki janrini kiriting
3. Bot sizga faylni yuboradi

❓ Savollar bo'lsa: @admin_username
"""
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['genres'])
def genres_command(message):
    """Janrlar ro'yxati"""
    genres = db.get_all_genres()
    if not genres:
        bot.send_message(message.chat.id, "❌ Hali hech qanday janr qo'shilmagan.")
        return
    
    text = "🎭 <b>Mavjud janrlar:</b>\n\n"
    for i, genre in enumerate(genres, 1):
        count = db.manhwas.count_documents({'genre': genre})
        text += f"{i}. {genre} ({count} ta)\n"
    
    text += "\nJanrni tanlash uchun /search komandasidan foydalaning."
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "📚 Barcha manhwalar")
def show_all_manhwas(message):
    """Barcha manhwalarni ko'rsatish"""
    is_subscribed, not_subscribed = check_subscription(message.from_user.id)
    if not is_subscribed:
        bot.send_message(
            message.chat.id,
            "❌ Iltimos, avval kanallarga obuna bo'ling!",
            reply_markup=get_subscription_keyboard(not_subscribed)
        )
        return
    
    result = db.get_all_manhwas(page=1, per_page=5)
    
    if not result['manhwas']:
        bot.send_message(message.chat.id, "❌ Hali hech qanday manhwa yuklanmagan.")
        return
    
    # Inline tugmalar yaratish
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for manhwa in result['manhwas']:
        btn_text = f"📖 {manhwa['title']} - Ch.{manhwa['chapter']}"
        keyboard.add(types.InlineKeyboardButton(
            btn_text, 
            callback_data=f"get_{manhwa['file_id']}"
        ))
    
    # Paginatsiya tugmalari
    if result['total_pages'] > 1:
        nav_buttons = []
        if result['page'] < result['total_pages']:
            nav_buttons.append(types.InlineKeyboardButton(
                "➡️ Keyingi", callback_data=f"page_{result['page'] + 1}"
            ))
        keyboard.add(*nav_buttons)
    
    bot.send_message(
        message.chat.id,
        f"📚 <b>Barcha manhwalar</b> (Jami: {result['total']} ta)\nSahifa: {result['page']}/{result['total_pages']}",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda m: m.text == "🔍 Qidirish")
def search_prompt(message):
    """Qidirish so'rovi"""
    msg = bot.send_message(
        message.chat.id,
        "🔍 Qidirmoqchi bo'lgan manhwa nomini yoki janrini yozing:"
    )
    bot.register_next_step_handler(msg, process_search)

def process_search(message):
    """Qidiruv natijalari"""
    query = message.text.strip()
    if not query:
        bot.send_message(message.chat.id, "❌ Iltimos, qidirish so'zini kiriting!")
        return
    
    results = db.search_manhwa(query, limit=10)
    
    if not results:
        bot.send_message(message.chat.id, f"❌ '{query}' bo'yicha hech narsa topilmadi.")
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for manhwa in results:
        btn_text = f"📖 {manhwa['title']} - Ch.{manhwa['chapter']}"
        keyboard.add(types.InlineKeyboardButton(
            btn_text,
            callback_data=f"get_{manhwa['file_id']}"
        ))
    
    bot.send_message(
        message.chat.id,
        f"🔍 '<b>{query}</b>' bo'yicha natijalar ({len(results)} ta):",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda m: m.text == "🎭 Janrlar")
def show_genres(message):
    """Janrlar menyusi"""
    genres = db.get_all_genres()
    if not genres:
        bot.send_message(message.chat.id, "❌ Hali janrlar mavjud emas.")
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for genre in genres:
        keyboard.add(types.InlineKeyboardButton(
            genre, callback_data=f"genre_{genre}"
        ))
    
    bot.send_message(message.chat.id, "🎭 <b>Janrni tanlang:</b>", reply_markup=keyboard)

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def show_stats(message):
    """Statistika"""
    stats = db.get_stats()
    text = f"""
📊 <b>Bot statistikasi</b>

📚 Jami manhwalar: <b>{stats['total_manhwas']}</b>
👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>
⬇️ Jami yuklab olishlar: <b>{stats['total_downloads']}</b>
"""
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def show_help(message):
    """Yordam menyusi"""
    help_command(message)

# ==================== Admin funksiyalari ====================

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin panel" and is_admin(m.from_user.id))
def admin_panel(message):
    """Admin paneli"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Siz admin emassiz!")
        return
    
    bot.send_message(
        message.chat.id,
        "⚙️ <b>Admin panel</b>\nQuyidagi amallardan birini tanlang:",
        reply_markup=get_admin_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "📤 Manhwa yuklash" and is_admin(m.from_user.id))
def upload_manhwa_prompt(message):
    """Manhwa yuklash uchun so'rov"""
    if not is_admin(message.from_user.id):
        return
    
    msg = bot.send_message(
        message.chat.id,
        "📤 <b>Manhwa faylini yuboring</b>\n\n"
        "Format: PDF, EPUB, CBZ, CBR, ZIP, RAR yoki rasm\n"
        "Bekor qilish uchun /cancel yozing"
    )
    bot.register_next_step_handler(msg, process_manhwa_file)

def process_manhwa_file(message):
    """Manhwa faylini qabul qilish"""
    if message.text and message.text.lower() == '/cancel':
        bot.send_message(message.chat.id, "❌ Yuklash bekor qilindi.", reply_markup=get_admin_keyboard())
        return
    
    # Fayl ma'lumotlarini olish
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or 'unknown'
        file_size = message.document.file_size
        media_type = 'document'
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = 'photo.jpg'
        file_size = message.photo[-1].file_size
        media_type = 'photo'
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or 'video.mp4'
        file_size = message.video.file_size
        media_type = 'video'
    else:
        bot.send_message(message.chat.id, "❌ Iltimos, fayl, rasm yoki video yuboring!")
        bot.register_next_step_handler(message, process_manhwa_file)
        return
    
    # Fayl ma'lumotlarini vaqtinchalik saqlash
    temp_data = {
        'file_id': file_id,
        'file_name': file_name,
        'file_size': file_size,
        'media_type': media_type
    }
    
    # Keyingi qadam - nom va chapter kiritish
    msg = bot.send_message(
        message.chat.id,
        "✅ Fayl qabul qilindi!\n\n"
        "Endi ma'lumotlarni quyidagi formatda yuboring:\n\n"
        "<code>Nomi | Chapter | Janr1, Janr2 | Tavsif</code>\n\n"
        "Masalan:\n"
        "<code>Solo Leveling | 150 | Action, Fantasy | Ajoyib manhwa</code>\n\n"
        "Bekor qilish uchun /cancel"
    )
    bot.register_next_step_handler(msg, process_manhwa_info, temp_data)

def process_manhwa_info(message, temp_data):
    """Manhwa ma'lumotlarini qayta ishlash"""
    if message.text and message.text.lower() == '/cancel':
        bot.send_message(message.chat.id, "❌ Yuklash bekor qilindi.", reply_markup=get_admin_keyboard())
        return
    
    try:
        parts = message.text.split('|')
        title = parts[0].strip() if len(parts) > 0 else 'Noma\'lum'
        chapter = parts[1].strip() if len(parts) > 1 else '1'
        genres = [g.strip() for g in parts[2].split(',')] if len(parts) > 2 else []
        description = parts[3].strip() if len(parts) > 3 else None
        
        # Ma'lumotlar bazasiga saqlash
        manhwa_id = db.add_manhwa(
            file_id=temp_data['file_id'],
            title=title,
            chapter=chapter,
            genre=genres,
            description=description,
            uploaded_by=message.from_user.id,
            file_name=temp_data['file_name'],
            file_size=temp_data['file_size'],
            media_type=temp_data['media_type']
        )
        
        if manhwa_id:
            success_text = f"""
✅ <b>Manhwa muvaffaqiyatli qo'shildi!</b>

📖 Nomi: <b>{title}</b>
📑 Chapter: <b>{chapter}</b>
🎭 Janr: {', '.join(genres) if genres else 'Ko\'rsatilmagan'}
📦 Hajm: {temp_data['file_size'] / 1024 / 1024:.1f} MB

ID: <code>{manhwa_id}</code>
"""
            bot.send_message(message.chat.id, success_text, reply_markup=get_admin_keyboard())
        else:
            bot.send_message(message.chat.id, "❌ Saqlashda xatolik yuz berdi!")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xato: {e}\nQaytadan urinib ko'ring.")
        bot.register_next_step_handler(message, process_manhwa_info, temp_data)

@bot.message_handler(func=lambda m: m.text == "❌ Manhwa o'chirish" and is_admin(m.from_user.id))
def delete_manhwa_prompt(message):
    """Manhwa o'chirish"""
    if not is_admin(message.from_user.id):
        return
    
    result = db.get_all_manhwas(page=1, per_page=20)
    if not result['manhwas']:
        bot.send_message(message.chat.id, "❌ O'chirish uchun manhwa yo'q.")
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for manhwa in result['manhwas']:
        keyboard.add(types.InlineKeyboardButton(
            f"❌ {manhwa['title']} - Ch.{manhwa['chapter']}",
            callback_data=f"delete_{manhwa['file_id']}"
        ))
    
    bot.send_message(
        message.chat.id,
        "🗑 <b>O'chirish uchun manhwani tanlang:</b>",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda m: m.text == "📋 Barcha manhwalar" and is_admin(m.from_user.id))
def admin_show_all(message):
    """Admin uchun barcha manhwalar"""
    if not is_admin(message.from_user.id):
        return
    show_all_manhwas(message)

@bot.message_handler(func=lambda m: m.text == "📊 To'liq statistika" and is_admin(m.from_user.id))
def admin_full_stats(message):
    """To'liq statistika"""
    if not is_admin(message.from_user.id):
        return
    
    stats = db.get_stats()
    users = db.get_all_users()
    
    text = f"""
📊 <b>To'liq statistika</b>

📚 Jami manhwalar: <b>{stats['total_manhwas']}</b>
👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>
⬇️ Jami yuklab olishlar: <b>{stats['total_downloads']}</b>

👤 <b>Oxirgi 10 ta foydalanuvchi:</b>
"""
    for user in users[-10:]:
        username = f"@{user.get('username')}" if user.get('username') else 'Noma\'lum'
        text += f"• {user.get('first_name', 'N/A')} ({username})\n"
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "📢 E'lon yuborish" and is_admin(m.from_user.id))
def broadcast_prompt(message):
    """E'lon yuborish"""
    if not is_admin(message.from_user.id):
        return
    
    msg = bot.send_message(
        message.chat.id,
        "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:"
    )
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    """E'lonni yuborish"""
    users = db.get_all_users()
    success = 0
    failed = 0
    
    for user in users:
        try:
            bot.send_message(user['user_id'], message.text)
            success += 1
        except:
            failed += 1
    
    bot.send_message(
        message.chat.id,
        f"📢 E'lon yuborildi!\n\n✅ Muvaffaqiyatli: {success}\n❌ Xato: {failed}"
    )

@bot.message_handler(func=lambda m: m.text == "⬅️ Asosiy menyu" and is_admin(m.from_user.id))
def back_to_main(message):
    """Asosiy menyuga qaytish"""
    bot.send_message(
        message.chat.id,
        "Asosiy menyu:",
        reply_markup=get_main_keyboard()
    )

# ==================== Callback handler ====================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Callback querylarni qayta ishlash"""
    user_id = call.from_user.id
    
    try:
        # Obuna tekshirish
        if call.data == "check_sub":
            is_subscribed, not_subscribed = check_subscription(user_id)
            if is_subscribed:
                bot.edit_message_text(
                    "✅ Obuna tasdiqlandi! Botdan foydalanishingiz mumkin.",
                    call.message.chat.id,
                    call.message.message_id
                )
                bot.send_message(
                    call.message.chat.id,
                    "Asosiy menyu:",
                    reply_markup=get_main_keyboard()
                )
            else:
                bot.answer_callback_query(call.id, "❌ Hali ham obuna bo'lmagansiz!", show_alert=True)
            return
        
        # Manhwa olish
        if call.data.startswith("get_"):
            file_id = call.data.replace("get_", "")
            manhwa = db.get_manhwa_by_file_id(file_id)
            
            if manhwa:
                send_manhwa_file(call.message.chat.id, manhwa)
                db.log_download(user_id, manhwa['title'], manhwa['chapter'])
                bot.answer_callback_query(call.id, "✅ Manhwa yuborildi!")
            else:
                bot.answer_callback_query(call.id, "❌ Manhwa topilmadi!", show_alert=True)
            return
        
        # Janr bo'yicha
        if call.data.startswith("genre_"):
            genre = call.data.replace("genre_", "")
            result = db.get_manhwas_by_genre(genre, page=1)
            
            if result['manhwas']:
                keyboard = types.InlineKeyboardMarkup(row_width=1)
                for manhwa in result['manhwas']:
                    keyboard.add(types.InlineKeyboardButton(
                        f"📖 {manhwa['title']} - Ch.{manhwa['chapter']}",
                        callback_data=f"get_{manhwa['file_id']}"
                    ))
                bot.edit_message_text(
                    f"🎭 <b>{genre}</b> janridagi manhwalar:",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard
                )
            else:
                bot.answer_callback_query(call.id, "❌ Bu janrda manhwa topilmadi!", show_alert=True)
            return
        
        # Paginatsiya
        if call.data.startswith("page_"):
            page = int(call.data.replace("page_", ""))
            result = db.get_all_manhwas(page=page)
            
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            for manhwa in result['manhwas']:
                keyboard.add(types.InlineKeyboardButton(
                    f"📖 {manhwa['title']} - Ch.{manhwa['chapter']}",
                    callback_data=f"get_{manhwa['file_id']}"
                ))
            
            nav_buttons = []
            if page > 1:
                nav_buttons.append(types.InlineKeyboardButton(
                    "⬅️ Oldingi", callback_data=f"page_{page - 1}"
                ))
            if page < result['total_pages']:
                nav_buttons.append(types.InlineKeyboardButton(
                    "➡️ Keyingi", callback_data=f"page_{page + 1}"
                ))
            if nav_buttons:
                keyboard.add(*nav_buttons)
            
            bot.edit_message_text(
                f"📚 <b>Barcha manhwalar</b> (Jami: {result['total']})\n"
                f"Sahifa: {page}/{result['total_pages']}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard
            )
            return
        
        # O'chirish
        if call.data.startswith("delete_") and is_admin(user_id):
            file_id = call.data.replace("delete_", "")
            if db.delete_manhwa(file_id):
                bot.edit_message_text(
                    "✅ Manhwa o'chirildi!",
                    call.message.chat.id,
                    call.message.message_id
                )
                bot.answer_callback_query(call.id, "✅ O'chirildi!")
            else:
                bot.answer_callback_query(call.id, "❌ Xatolik!", show_alert=True)
            return
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi!", show_alert=True)

# ==================== Flask webhook ====================

@app.route('/')
def index():
    return 'Bot is running! ✅'

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad request', 400

@app.route('/set_webhook')
def set_webhook():
    """Webhook o'rnat
