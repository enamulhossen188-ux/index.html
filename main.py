import telebot
from telebot import types
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import json
import os
from datetime import datetime
import time
# আপনার বটের টোকেন এবং টেলিগ্রাম আইডি
BOT_TOKEN = "8995171178:AAGNwil6GNUEVDSvN3XbneR9CZFYhtZleWw"
ADMIN_ID = 7255626228  # আপনার সংখ্যাযুক্ত টেলিগ্রাম আইডি

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

DB_FILE = "database.json"

# ডাটাবেজ হ্যান্ডলিং
def load_data():
    if not os.path.exists(DB_FILE):
        default_data = {
            "users": [],
            "ads": {
                "ad1": "https://google.com",
                "ad2": "https://google.com"
            },
            "videos": []
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)
        return default_data
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

admin_state = {}

# API: মিনি অ্যাপের জন্য ডাটা দেওয়া
@app.route('/api/data', methods=['GET'])
def get_app_data():
    return jsonify(load_data())

@app.route('/')
def home():
    return "Bot Server is Live 24/7!"

# /start কমান্ড (ডিপলিংক, ২৪ ঘণ্টা লক ও সাধারণ স্টার্ট)
@bot.message_handler(commands=['start'])
def send_welcome(message):
    data = load_data()
    user_id = message.chat.id
    if "users" not in data:
        data["users"] = []
    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)

    # ভিডিও হিস্ট্রি ও টাইমার ট্র্যাকিং ডাটাবেজ
    if "download_history" not in data:
        data["download_history"] = {}

    # যদি ভিডিও ডাউনলোডের রিকোয়েস্ট নিয়ে স্টার্ট আসে
    text_parts = message.text.split()
    if len(text_parts) > 1 and text_parts[1].startswith("vid_"):
        video_id = text_parts[1].replace("vid_", "")
        target_video = None
        for v in data.get("videos", []):
            if str(v.get("id")) == str(video_id):
                target_video = v
                break

        if target_video:
            user_key = f"{user_id}_{video_id}"
            current_time = time.time()
            last_download_time = data["download_history"].get(user_key, 0)
            
            # ২৪ ঘণ্টা = ৮৬৪০০ সেকেন্ড
            lock_duration = 24 * 3600
            time_left = lock_duration - (current_time - last_download_time)

            if time_left > 0:
                hours = int(time_left // 3600)
                minutes = int((time_left % 3600) // 60)
                bot.send_message(
                    message.chat.id,
                    f"🔒 **ভিডিওটি সাময়িকভাবে লক করা আছে!**\n\n"
                    f"আপনি ইতিমধ্যে **{target_video['title']}** ভিডিওটি পেয়েছেন।\n"
                    f"⏳ পুনরায় ডাউনলোড করতে অপেক্ষা করুন: **{hours} ঘণ্টা {minutes} মিনিট**।"
                )
                return

            # প্রথমবার বা ২৪ ঘণ্টা পর ভিডিও ডেলিভারি
            bot.send_message(message.chat.id, f"🎬 **{target_video['title']}**\n⏳ আপনার ভিডিওটি পাঠানো হচ্ছে...")
            try:
                bot.send_video(message.chat.id, target_video['file_id'])
                data["download_history"][user_key] = current_time
                save_data(data)
            except Exception:
                try:
                    bot.send_document(message.chat.id, target_video['file_id'])
                    data["download_history"][user_key] = current_time
                    save_data(data)
                except Exception:
                    bot.send_message(message.chat.id, "❌ ভিডিওটি পাঠাতে সমস্যা হচ্ছে। অ্যাডমিনের সাথে যোগাযোগ করুন।")
            return
        else:
            bot.send_message(message.chat.id, "❌ দুঃখিত, ভিডিওটি খুঁজে পাওয়া যায়নি!")
            return

    # সাধারণ /start হলে মেনু দেখানো
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎬 WATCH NOW", web_app=types.WebAppInfo(url="https://enamulhossen188-ux.github.io/index.html/")),
        types.InlineKeyboardButton("🔔 VIDEO UPDATE", callback_data="btn_update"),
        types.InlineKeyboardButton("🗣️ যেভাবে ভিডিও ডাউনলোড করবেন", callback_data="btn_help")
    )

    welcome_text = (
        f"**আসসালামু আলাইকুম {message.from_user.first_name}** 🥰\n\n"
        "আমাদের বট ২৪ ঘণ্টা সচল। ভিডিও ডাউনলোড করতে নিচের **WATCH NOW** বাটনে ক্লিক করুন।"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == "btn_update":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📢 **ভিডিও আপডেট:**\nনতুন পর্ব আপলোড করা হয়েছে! স্টার্ট দিয়ে Watch Now থেকে দেখে নিন।", parse_mode="Markdown")
    elif call.data == "btn_help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "💡 **টিউটোরিয়াল:**\nWatch Now বাটনে ক্লিক করে যে ভিডিও দেখতে চান সেটিতে চাপুন। দুটি টাস্ক ১০ সেকেন্ড ভিজিট করে ডাউনলোড বাটনে চাপ দিলেই ভিডিও পেয়ে যাবেন।")

# ইনবক্সে সব ইউজারকে মেসেজ/আপডেট পাঠানোর কমান্ড
@bot.message_handler(commands=['broadcast'])
def broadcast_start(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "দুঃখিত, আপনি অ্যাডমিন নন!")
        return
    admin_state[message.chat.id] = {'step': 'broadcast_msg'}
    bot.send_message(message.chat.id, "📢 **সকল ইউজারের ইনবক্সে কী আপডেট বা মেসেজ পাঠাতে চান, তা লিখে পাঠান:**")

# অ্যাডমিন এড লিংক সেট করা
@bot.message_handler(commands=['setads'])
def set_ads_start(message):
    if message.chat.id != ADMIN_ID:
    admin_state[message.chat.id] = {'step': 'ad1'}
    bot.send_message(message.chat.id, "🎯 **Task 1 এর এড লিংক পাঠান:**")

# নতুন ভিডিও আপলোড
@bot.message_handler(commands=['upload'])
def start_upload(message):

    if message.chat.id != ADMIN_ID:
        return
    admin_state[message.chat.id] = {'step': 'category'}
    
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("BPS5", "Web Series", "Movie")
    bot.send_message(message.chat.id, "📂 **ভিডিওর ক্যাটাগরি বেছে নিন:**", reply_markup=markup)

# অ্যাডমিন প্রসেস কন্ট্রোলার
@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_admin_inputs(message):
    chat_id = message.chat.id 
    if chat_id != ADMIN_ID or chat_id not in admin_state:
        return

    step = admin_state[chat_id].get('step')

    # ব্রডকাস্ট নোটিশ সেন্ডিং
    if step == 'broadcast_msg' and message.text:
        text_to_send = message.text
        data = load_data()
        user_list = data.get("users", [])
        bot.send_message(chat_id, f"🚀 {len(user_list)} জন ইউজারের কাছে নোটিশ পাঠানো শুরু হচ্ছে...")
        
        sent_count = 0
        for uid in user_list:
            try:
                bot.send_message(uid, f"📢 **ভিডিও আপডেট:**\n\n{text_to_send}", parse_mode="Markdown")
                sent_count += 1
            except Exception:
                pass
        
        del admin_state[chat_id]
        bot.send_message(chat_id, f"✅ সফলভাবে {sent_count} জন ইউজারের ইনবক্সে আপডেট পৌঁছে গেছে!")

    # এড লিংক সেট
    elif step == 'ad1' and message.text:
        admin_state[chat_id]['ad1'] = message.text.strip()
        admin_state[chat_id]['step'] = 'ad2'
        bot.send_message(chat_id, "✅ Task 1 সেভ হয়েছে!\n🎯 এবার **Task 2 এর এড লিংক পাঠান:**")

    elif step == 'ad2' and message.text:
        ad2_link = message.text.strip()
        data = load_data()
        data['ads']['ad1'] = admin_state[chat_id]['ad1']
        data['ads']['ad2'] = ad2_link
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "🎉 **দুটি এড লিংকই সেভ হয়ে গেছে!**")

    # আপলোড ফ্লো
    elif step == 'category' and message.text:
        admin_state[chat_id]['category'] = message.text.strip()
        admin_state[chat_id]['step'] = 'title'
        bot.send_message(chat_id, "🎬 **ভিডিওর নাম (Title) লিখুন:**\n(যেমন: Bachelor Point Season [5] Episode 120)", reply_markup=types.ReplyKeyboardRemove())

    elif step == 'title' and message.text:
        admin_state[chat_id]['title'] = message.text.strip()
        admin_state[chat_id]['step'] = 'thumb'
        bot.send_message(chat_id, "🖼️ **থাম্বনেইল ছবি পাঠান:**")

    elif step == 'thumb' and (message.photo or message.text):
        if message.photo:
            file_info = bot.get_file(message.photo[-1].file_id)
            thumb_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        else:
            thumb_url = message.text.strip()

        admin_state[chat_id]['thumb'] = thumb_url
        admin_state[chat_id]['step'] = 'video'
        bot.send_message(chat_id, "📥 **ভিডিও ফাইলটি সেন্ড বা ফরোয়ার্ড করুন:**")

    elif step == 'video' and (message.video or message.document):
        file_id = message.video.file_id if message.video else message.document.file_id
        data = load_data()
        
        new_video = {
            "id": len(data['videos']) + 1,
            "category": admin_state[chat_id]['category'],
            "title": admin_state[chat_id]['title'],
            "thumb": admin_state[chat_id]['thumb'],
            "file_id": file_id,
            "date": datetime.now().strftime("%b %d, %Y")
        }
        data['videos'].insert(0, new_video)
        save_data(data)

        title_done = admin_state[chat_id]['title']
        del admin_state[chat_id]
        bot.reply_to(message, f"🎉 **{title_done} সফলভাবে আপলোড হয়েছে!**\nমিনি অ্যাপে এখনই দেখা যাচ্ছে।")

# মিনি অ্যাপ ডাউনলোড হ্যান্ডলার
@bot.message_handler(content_types=['web_app_data'])
def handle_webapp_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        if data.get('action') == 'send_video':
            file_id = data.get('file_id')
            bot.send_message(message.chat.id, "⏳ আপনার ভিডিওটি পাঠানো হচ্ছে...")
            bot.send_video(message.chat.id, file_id)
    except Exception as e:
        bot.send_message(message.chat.id, "ভিডিওটি পাঠাতে সমস্যা হচ্ছে। আবার চেষ্টা করুন।")

def run_flask():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.start()
    bot.infinity_polling()
