import telebot
from telebot import types
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import json
import os
from datetime import datetime
import time

BOT_TOKEN = "8995171178:AAGNwil6GNUEVDSvN3XbneR9CZFYhtZleWw"
ADMIN_ID = 7255626228  # আপনার টেলিগ্রাম আইডি

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

DB_FILE = "database.json"

# ডাটাবেজ ব্যাকআপ ও হ্যান্ডলিং লজিক
def load_data():
    if not os.path.exists(DB_FILE):
        default_data = {
            "users": [],
            "ads": {
                "ad1": "https://google.com",
                "ad2": "https://google.com"
            },
            "videos": [],
            "download_history": {}
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)
        return default_data
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": [], "ads": {"ad1": "https://google.com", "ad2": "https://google.com"}, "videos": [], "download_history": {}}

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # অ্যাডমিন চ্যাটে স্বয়ংক্রিয় ব্যাকআপ ফাইল পাঠানো (যাতে ডেটা কখনো না হারায়)
    try:
        with open(DB_FILE, "rb") as f:
            bot.send_document(ADMIN_ID, f, caption="💾 Auto Backup: Database Updated")
    except Exception as e:
        print(f"Auto Backup Error: {e}")

admin_state = {}

# API: মিনি অ্যাপের জন্য ডাটা দেওয়া
@app.route('/api/data', methods=['GET'])
def get_app_data():
    return jsonify(load_data())

@app.route('/')
def home():
    return "Bot Server is Live 24/7!"

# /start কমান্ড
@bot.message_handler(commands=['start'])
def send_welcome(message):
    data = load_data()
    user_id = message.chat.id
    if "users" not in data:
        data["users"] = []
    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)

    if "download_history" not in data:
        data["download_history"] = {}

    # ডিপলিংক চেক
    text_parts = message.text.split()
    if len(text_parts) > 1 and text_parts[1].startswith("vid_"):
        video_id = text_parts[1].replace("vid_", "")
        target_video = next((v for v in data.get("videos", []) if str(v.get("id")) == str(video_id)), None)

        if target_video:
            user_key = f"{user_id}_{video_id}"
            current_time = time.time()
            last_download_time = data["download_history"].get(user_key, 0)
            
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

    # সাধারণ /start কিবোর্ড
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎬 WATCH NOW", web_app=types.WebAppInfo(url="https://enamulhossen188-ux.github.io/index.html?v=3")),
        types.InlineKeyboardButton("🔔 VIDEO UPDATE", callback_data="btn_update"),
        types.InlineKeyboardButton("💡 যেভাবে ভিডিও ডাউনলোড করবেন", callback_data="btn_help")
    )       

    welcome_text = (
        f"**আসসালামু আলাইকুম {message.from_user.first_name}** 🥰\n\n"
        "আমাদের বট ২৪ ঘণ্টা সচল। ভিডিও দেখতে ও ডাউনলোড করতে নিচের **WATCH NOW** বাটনে ক্লিক করুন।"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == "btn_update":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📢 **ভিডিও আপডেট:**\nনতুন পর্ব আপলোড করা হয়েছে! স্টার্ট দিয়ে Watch Now থেকে দেখে নিন।", parse_mode="Markdown")
    elif call.data == "btn_help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "💡 **টিউটোরিয়াল:**\nWatch Now বাটনে ক্লিক করে যে ভিডিও দেখতে চান সেটিতে চাপুন। দুটি টাস্ক ১০ সেকেন্ড ভিজিট করে ডাউনলোড বাটনে চাপ দিলেই ইনবক্সে ভিডিও পেয়ে যাবেন।")

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
        return
    admin_state[message.chat.id] = {'step': 'ad1'}
    bot.send_message(message.chat.id, "🎯 **Task 1 এর এড লিংক পাঠান:**")

# নতুন ভিডিও আপলোড
@bot.message_handler(commands=['upload'])
def start_upload(message):
    current_id = str(message.chat.id)
    target_id = str(ADMIN_ID)
    
    if current_id != target_id:
        bot.reply_to(message, f"❌ দুঃখিত! আপনি অ্যাডমিন নন।\nআপনার আইডি: `{current_id}`\nপ্রয়োজনীয় আইডি: `{target_id}`", parse_mode="Markdown")
        return
        
    admin_state[message.chat.id] = {'step': 'category'}
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("BPS5", "Web Series", "Movie")
    bot.send_message(message.chat.id, "📁 **ভিডিওর ক্যাটাগরি বেছে নিন:**", reply_markup=markup, parse_mode="Markdown")

# ডাটাবেজ ব্যাকআপ ফাইল থেকে রিস্টোর করার অপশন (প্রয়োজনে অ্যাডমিন database.json ফাইল পাঠালে তা সেভ হয়ে যাবে)
@bot.message_handler(content_types=['document'])
def handle_db_restore(message):
    if message.chat.id == ADMIN_ID and message.document.file_name == "database.json":
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            with open(DB_FILE, "wb") as f:
                f.write(downloaded_file)
            bot.reply_to(message, "✅ **Database সফলভাবে Restore করা হয়েছে!** সব ভিডিও আবার যুক্ত হয়ে গেছে।")
            return
        except Exception as e:
            bot.reply_to(message, f"❌ Restore Error: {e}")
            return
    # যদি ব্যাকআপ ফাইল না হয়, তবে সাধারণ হ্যান্ডলারে যাবে
    handle_admin_inputs(message)

# অ্যাডমিন প্রসেস কন্ট্রোলার
@bot.message_handler(content_types=['text', 'photo', 'video'])
def handle_admin_inputs(message):
    chat_id = message.chat.id 
    if chat_id != ADMIN_ID or chat_id not in admin_state:
        return

    step = admin_state[chat_id].get('step')

    # ব্রডকাস্ট নোটিশ
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

# মিনি অ্যাপ থেকে ডাউনলোড ট্রিগার হলে ইনবক্সে সরাসরি ভিডিও পাঠানোর হ্যান্ডলার
@bot.message_handler(content_types=['web_app_data'])
def handle_webapp_data(message):
    try:
        payload = json.loads(message.web_app_data.data)
        data = load_data()
        
        # মিনি অ্যাপ থেকে আসা video_id বা file_id হ্যান্ডল করা
        v_id = payload.get('video_id')
        target_video = None
        
        if v_id:
            target_video = next((v for v in data.get("videos", []) if str(v.get("id")) == str(v_id)), None)
            
        file_id = target_video['file_id'] if target_video else payload.get('file_id')

        if file_id:
            bot.send_message(message.chat.id, "⏳ আপনার ভিডিওটি পাঠানো হচ্ছে...")
            try:
                caption = f"🎬 **{target_video['title']}**\n\nউপভোগ করুন!" if target_video else ""
                bot.send_video(message.chat.id, file_id, caption=caption, parse_mode="Markdown")
            except Exception:
                bot.send_document(message.chat.id, file_id)
        else:
            bot.send_message(message.chat.id, "❌ ভিডিওটি খুঁজে পাওয়া যায়নি!")
    except Exception as e:
        print(f"WebApp Data Error: {e}")
        bot.send_message(message.chat.id, "❌ ভিডিওটি পাঠাতে সমস্যা হয়েছে। আবার চেষ্টা করুন।")

def run_flask():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.start()
    bot.infinity_polling()
