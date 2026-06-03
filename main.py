import os
import telebot
from flask import Flask, request
from pymongo import MongoClient
from datetime import datetime
import logging

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask ilovasi
app = Flask(__name__)

# Telegram bot token
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN topilmadi!")

bot = telebot.TeleBot(TOKEN)

# MongoDB Atlas ulanish
MONGO_URI = os.environ.get('MONGO_URI')
try:
    client = MongoClient(MONGO_URI)
    db = client['telegram_bot']
    users_collection = db['users']
    logger.info("MongoDB ga ulanish muvaffaqiyatli!")
except Exception as e:
    logger.error(f"MongoDB ulanishda xatolik: {e}")

# Bot komandalari
@bot.message_handler(commands=['start'])
def send_welcome(message):
    logger.info(f"Start komandasi qabul qilindi: {message.from_user.id}")
    
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        
        # Foydalanuvchini bazaga saqlash
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'joined_date': datetime.now(),
            'last_active': datetime.now()
        }
        
        # Bazaga saqlash
        existing_user = users_collection.find_one({'user_id': user_id})
        if not existing_user:
            users_collection.insert_one(user_data)
            logger.info(f"Yangi foydalanuvchi qo'shildi: {user_id}")
        else:
            users_collection.update_one(
                {'user_id': user_id},
                {'$set': {'last_active': datetime.now(), 'username': username, 'first_name': first_name}}
            )
            logger.info(f"Foydalanuvchi yangilandi: {user_id}")
        
        # Javob
        welcome_text = f"""
🚀 Salom {first_name}! Botimizga xush kelibsiz!

Bot hali rivojlanish bosqichida. Tez orada yangi funksiyalar qo'shiladi.

📋 Mavjud komandalar:
/start - Botni qayta ishga tushirish
/help - Yordam olish
        """
        
        bot.reply_to(message, welcome_text)
        logger.info("Start javobi yuborildi")
        
    except Exception as e:
        logger.error(f"Start komandasida xatolik: {e}")
        bot.reply_to(message, "Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
🤖 Bot haqida ma'lumot:
Bu bot MongoDB Atlas bilan ishlaydi va Render.com da joylashtirilgan.

🔧 Texnik ma'lumotlar:
- Python (TeleBot + Flask)
- MongoDB Atlas
- Render.com hosting
    """
    bot.reply_to(message, help_text)

# Barcha xabarlarni ushlash
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    logger.info(f"Yangi xabar: {message.text}")
    bot.reply_to(message, f"Siz yozdingiz: {message.text}")

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            logger.info(f"Webhook ma'lumot qabul qilindi: {json_string[:200]}...")
            
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return 'OK', 200
        else:
            logger.warning("Noto'g'ri content type")
            return 'Bad Request', 403
    except Exception as e:
        logger.error(f"Webhook xatolik: {e}")
        return 'Error', 500

@app.route('/')
def index():
    return 'Bot is running! ✅'

# Webhook o'rnatish
@app.route('/set_webhook')
def set_webhook():
    try:
        # Render.com dagi to'liq URL
        webhook_url = f"https://adult-manhwa-bot.onrender.com/webhook"
        
        # Eski webhookni o'chirish
        bot.remove_webhook()
        
        # Yangi webhook o'rnatish
        result = bot.set_webhook(url=webhook_url)
        
        logger.info(f"Webhook o'rnatildi: {result}")
        return f"Webhook set to {webhook_url} ✅ Result: {result}"
    except Exception as e:
        logger.error(f"Webhook o'rnatishda xatolik: {e}")
        return f"Error setting webhook: {e}"

# Webhook ma'lumotlarini ko'rish
@app.route('/webhook_info')
def webhook_info():
    try:
        info = bot.get_webhook_info()
        return f"Webhook info: {info}"
    except Exception as e:
        return f"Error: {e}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
