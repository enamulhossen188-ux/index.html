import telebot
from telebot import types
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading

# এখানে আপনার বটের টোকেন এবং টেলিগ্রাম ইউজার আইডি বসাবেন
BOT_TOKEN = "8995171178:AAGNwil6GNUEVDSvN3XbneR9CZFYhtZleWw"
ADMIN_ID = 7255626228  # আপনার সংখ্যাযুক্ত আইডি

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

admin_state = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        f"আসসালামু আলাইকুম {message.from_user.first_name}!\n\nভিডিও দেখতে নিচে বাঁ পাশের 🎬 **WATCH NOW** বাটনে ক্লিক করুন।"
    )

@bot.message_handler(commands=['upload'])
def start_upload(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "দুঃখিত, আপনি অ্যাডমিন নন!")
        return
    admin_state[message.chat.id] = {'step': 'file'}
    bot.send_message(message.chat.id, "আপনি যে ভিডিওটি সেভ করতে চান, সেটি এখানে পাঠান বা ফরোয়ার্ড করুন:")

@bot.message_handler(content_types=['video', 'document'], func=lambda msg: msg.chat.id in admin_state and admin_state[msg.chat.id].get('step') == 'file')
def get_video_file(message):
    file_id = message.video.file_id if message.video else message.document.file_id
    del admin_state[message.chat.id]
    
    bot.reply_to(
        message, 
        f"✅ ভিডিওটি সফলভাবে সিস্টেমে যুক্ত হয়েছে!\n\nএই ভিডিওর File ID:\n`{file_id}`\n\n(এটি কপি করে আপনার মিনি অ্যাপে ব্যবহার করতে পারবেন)",
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['web_app_data'])
def handle_webapp_data(message):
    import json
    try:
        data = json.loads(message.web_app_data.data)
        if data.get('action') == 'send_video':
            file_id = data.get('file_id')
            bot.send_message(message.chat.id, "⏳ আপনার ভিডিওটি পাঠানো হচ্ছে...")
            bot.send_video(message.chat.id, file_id)
    except Exception as e:
        bot.send_message(message.chat.id, "ভিডিওটি পাঠাতে সমস্যা হচ্ছে। আবার চেষ্টা করুন।")

@app.route('/')
def home():
    return "Bot Server is Running Live 24/7!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.start()
    bot.infinity_polling()
