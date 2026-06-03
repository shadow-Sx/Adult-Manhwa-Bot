import os
import telebot
from flask import Flask, request
from pymongo import MongoClient
from datetime import datetime

# Flask ilovasi
app = Flask(__name__)

# Telegram bot token (Render env dan olinadi)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

# MongoDB Atlas ulanish
MONGO_URI = os.environ.get('MONGO_URI')
client = MongoClient(MONGO_URI)
db = client['telegram_bot']
users_collection = db['users']

# Webhook URL
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')  # Renderda https://your-app.onrender.com

# Bot komandalari
@bot.message_handler(commands=['start'])
def send_welcome(message):
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
    
    # Agar foydalanuvchi bazada bo'lmasa qo'shamiz
    if not users_collection.find_one({'user_id': user_id}):
        users_collection.insert_one(user_data)
    else:
        # Mavjud foydalanuvchini yangilash
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'last_active': datetime.now(), 'username': username, 'first_name': first_name}}
        )
    
    # Foydalanuvchiga javob
    welcome_text = f"""
🚀 Salom {first_name}! Botimizga xush kelibsiz!

Bot hali rivojlanish bosqichida. Tez orada yangi funksiyalar qo'shiladi.

📋 Mavjud komandalar:
/start - Botni qayta ishga tushirish
/help - Yordam olish
    """
    
    bot.reply_to(message, welcome_text)

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

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    else:
        return 'Bad Request', 403

@app.route('/')
def index():
    return 'Bot is running! ✅'

# Webhook o'rnatish
@app.route('/set_webhook')
def set_webhook():
    webhook_url = f"{WEBHOOK_URL}/webhook"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    return f"Webhook set to {webhook_url} ✅"

if __name__ == '__main__':
    # Lokal development uchun polling
    if os.environ.get('ENVIRONMENT') == 'development':
        print("Bot polling mode...")
        bot.polling(none_stop=True)
    else:
        # Production uchun webhook
        pass  # gunicorn orqali ishlaydi
