import telebot
from telebot import types
from flask import Flask, jsonify, make_response
from flask_cors import CORS
import threading
import json
import os
from datetime import datetime

BOT_TOKEN = "8995171178:AAGtywmRpI9PNlhXJ2Swdb6r-8T8nXEcqu0"
ADMIN_ID = 7255626228

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

DB_FILE = "database.json"

import base64
import requests

GITHUB_TOKEN = "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"
REPO_NAME = "enamulhossen188-ux/index.html"
FILE_PATH = "database.json"

def get_github_db():
    try:
        url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return json.loads(content), r.json()['sha']
    except Exception as e:
        print("GitHub Read Error:", e)
    return None, None

def load_data():
    data, _ = get_github_db()
    if data:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    default_data = {
        "users": [],
        "ads": {"ad1": "https://google.com", "ad2": "https://google.com"},
        "videos": []
    }
    return default_data

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    try:
        url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        _, sha = get_github_db()
        content_str = json.dumps(data, ensure_ascii=False, indent=2)
        content_b64 = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')

        payload = {
            "message": "Auto update database [Bot Cloud]",
            "content": content_b64
        }
        if sha:
            payload["sha"] = sha

        requests.put(url, headers=headers, json=payload)
    except Exception as e:
        print("GitHub Save Error:", e)
            
admin_state = {}

# ফাস্ট এপিআই
@app.route('/api/data', methods=['GET'])
def get_app_data():
    data = load_data()
    resp = make_response(jsonify(data))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

@app.route('/')
def home():
    return "Bot Server is Live 24/7!"

@bot.message_handler(commands=['cancel'])
def cancel_process(message):
    chat_id = message.chat.id
    if chat_id in admin_state:
        del admin_state[chat_id]
        bot.send_message(chat_id, "🔄 আগের অসমাপ্ত কাজ বাতিল করা হয়েছে।", reply_markup=types.ReplyKeyboardRemove())
    else:
        bot.send_message(chat_id, "বর্তমানে কোনো কাজ চালু নেই।")
@bot.message_handler(commands=['broadcast'])
def broadcast_start(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ আপনি অ্যাডমিন নন!")
        return
    admin_state[message.chat.id] = {'step': 'broadcast_content'}
    bot.send_message(
        message.chat.id, 
        "📢 **ব্রডকাস্ট পোস্টটি পাঠান:**\n\nআপনি যে ছবিটি পাঠাতে চান সেটি ক্যাপশন সহ পাঠান। বট নিজে থেকেই নিচে **WATCH NOW** বাটন যুক্ত করে সবার ইনবক্সে পাঠিয়ে দেবে।"
    )

@bot.message_handler(commands=['setads'])
def set_ads_start(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ আপনি অ্যাডমিন নন!")
        return
    admin_state[message.chat.id] = {'step': 'ad1'}
    bot.send_message(message.chat.id, "🎯 **Task 1 এর এড লিংক পাঠান:**")
@bot.message_handler(commands=['delete'])
def delete_start(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ আপনি অ্যাডমিন নন!")
        return
    data = load_data()
    videos = data.get("videos", [])
    if not videos:
        bot.send_message(message.chat.id, "ℹ️ ডাটাবেজে কোনো ভিডিও নেই!")
        return
    markup = types.InlineKeyboardMarkup()
    for v in videos:
        markup.add(types.InlineKeyboardButton(f"🗑️ {v.get('title', 'Unknown')}", callback_data=f"del_{v.get('id')}"))
    bot.send_message(message.chat.id, "🗑️ **কোন ভিডিওটি ডিলিট করতে চান? ক্লিক করুন:**", reply_markup=markup)
@bot.message_handler(commands=['upload'])
def start_upload(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.reply_to(message, f"❌ আপনি অ্যাডমিন নন! আপনার আইডি: `{message.chat.id}`", parse_mode="Markdown")
        return
        
    admin_state[message.chat.id] = {'step': 'category'}
    data = load_data()
    cats = data.get("categories", ["BPS5", "Web Series", "Movie"])
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for i in range(0, len(cats), 2):
        row = [types.KeyboardButton(c) for c in cats[i:i+2]]
        markup.row(*row)
    markup.row(types.KeyboardButton("/cancel"))
    bot.send_message(message.chat.id, "📁 **ভিডিওর ক্যাটাগরি বেছে নিন:**", reply_markup=markup, parse_mode="Markdown")

# /start এবং সরাসরি ইনবক্সে ভিডিও ডেলিভারি
@bot.message_handler(commands=['start'])
def send_welcome(message):
    data = load_data()
    user_id = message.chat.id
    if "users" not in data:
        data["users"] = []
    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)

    text_parts = message.text.split()
    if len(text_parts) > 1 and text_parts[1].startswith("vid_"):
        video_id = text_parts[1].replace("vid_", "")
        target_video = next((v for v in data.get("videos", []) if str(v.get("id")) == str(video_id)), None)

        if target_video:
            bot.send_message(message.chat.id, f"🎬 **{target_video['title']}**\n⏳ আপনার ভিডিওটি ইনবক্সে পাঠানো হচ্ছে...")
            try:
                caption = f"🎬 **{target_video['title']}**\n\nউপভোগ করুন!"
                bot.send_video(message.chat.id, target_video['file_id'], caption=caption, parse_mode="Markdown")
            except Exception:
                try:
                    bot.send_document(message.chat.id, target_video['file_id'])
                except Exception:
                    bot.send_message(message.chat.id, "❌ ভিডিওটি পাঠাতে সমস্যা হচ্ছে।")
            return
        else:
            bot.send_message(message.chat.id, "❌ দুঃখিত, ভিডিওটি পাওয়া যায়নি!")
            return

    fresh_url = f"https://enamulhossen188-ux.github.io/index.html?ts={int(datetime.now().timestamp())}"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎬 WATCH NOW", web_app=types.WebAppInfo(url=fresh_url)),
        types.InlineKeyboardButton("🔔 VIDEO UPDATE", callback_data="btn_update"),
        types.InlineKeyboardButton("💡 যেভাবে ভিডিও ডাউনলোড করবেন", callback_data="btn_help")
    )       

    welcome_text = (
        f"**আসসালামু আলাইকুম {message.from_user.first_name}** 🥰\n\n"
        "আমাদের বট ২৪ ঘণ্টা সচল। নাটক দেখতে ও ডাউনলোড করতে নিচের **WATCH NOW** বাটনে ক্লিক করুন।"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)

def handle_callbacks(call):
    if call.data.startswith("del_"):
        if str(call.message.chat.id) != str(ADMIN_ID):
            bot.answer_callback_query(call.id, "❌ অনুমতি নেই!")
            return
        target_id = call.data.replace("del_", "")
        data = load_data()
        videos = data.get("videos", [])
        new_videos = [v for v in videos if str(v.get("id")) != str(target_id)]
        if len(new_videos) < len(videos):
            data["videos"] = new_videos
            save_data(data)
            bot.answer_callback_query(call.id, "✅ মুছে ফেলা হয়েছে!")
            bot.edit_message_text("✅ **ভিডিওটি সফলভাবে ডিলিট করা হয়েছে!**", chat_id=call.message.chat.id, message_id=call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ পাওয়া যায়নি!")
        return
    if call.data == "btn_update":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📢 **ভিডিও আপডেট:**\nনতুন পর্ব আপলোড করা হয়েছে! স্টার্ট দিয়ে Watch Now থেকে দেখে নিন।", parse_mode="Markdown")
    elif call.data == "btn_help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "💡 **টিউটোরিয়াল:**\nWatch Now বাটনে ক্লিক করে পছন্দের ভিডিওতে চাপুন। দুটি টাস্ক ১০ সেকেন্ড ভিজিট করে ডাউনলোড বাটনে চাপ দিলেই ইনবক্সে ভিডিও চলে আসবে।")

@bot.message_handler(content_types=['text', 'photo', 'video'])
def handle_admin_inputs(message):
    chat_id = message.chat.id 
    if str(chat_id) != str(ADMIN_ID) or chat_id not in admin_state:
        return

    step = admin_state[chat_id].get('step')

    if step == 'broadcast_content':
        data = load_data()
        user_list = data.get("users", [])
        bot.send_message(chat_id, f"🚀 {len(user_list)} জনের ইনবক্সে পোস্ট পাঠানো হচ্ছে...")
        sent_count = 0

        # ওয়াচ নাও বাটন তৈরি
        fresh_url = f"https://enamulhossen188-ux.github.io/index.html?ts={int(datetime.now().timestamp())}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎬 WATCH NOW", web_app=types.WebAppInfo(url=fresh_url)))

        for uid in user_list:
            try:
                if message.photo:
                    bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "", reply_markup=markup, parse_mode="Markdown")
                elif message.video:
                    bot.send_video(uid, message.video.file_id, caption=message.caption or "", reply_markup=markup, parse_mode="Markdown")
                elif message.text:
                    bot.send_message(uid, message.text, reply_markup=markup, parse_mode="Markdown")
                sent_count += 1
            except Exception:
                pass

        del admin_state[chat_id]
        bot.send_message(chat_id, f"✅ সফলভাবে {sent_count} জনের ইনবক্সে WATCH NOW বাটনসহ পোস্ট চলে গেছে!")
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

    elif step == 'category' and message.text:
        admin_state[chat_id]['category'] = message.text.strip()
        admin_state[chat_id]['step'] = 'title'
        bot.send_message(chat_id, "🎬 **ভিডিওর নাম (Title) লিখুন:**", reply_markup=types.ReplyKeyboardRemove())

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
        
        # সহজ সিরিয়াল আইডি যাতে কোনো মিসম্যাচ না হয়
        new_id = len(data.get('videos', [])) + 1
        new_video = {
            "id": new_id,
            "category": admin_state[chat_id]['category'],
            "title": admin_state[chat_id]['title'],
            "thumb": admin_state[chat_id]['thumb'],
            "file_id": file_id,
            "date": datetime.now().strftime("%b %d, %Y")
        }
        
        if "videos" not in data:
            data["videos"] = []
        data['videos'].insert(0, new_video)
        save_data(data)

        title_done = admin_state[chat_id]['title']
        del admin_state[chat_id]
        bot.reply_to(message, f"🎉 **{title_done} সফলভাবে আপলোড হয়েছে!**\nমিনি অ্যাপে এখনই দেখতে পাবেন।")
# --- ক্যাটাগরি ম্যানেজমেন্ট ---
@bot.message_handler(commands=['setcategory'])
def manage_categories_menu(message):
    try:
        data = load_data()
        cats = data.get("categories")
        if not cats or not isinstance(cats, list):
            cats = ["BPS5", "Web Series", "Movie"]
            data["categories"] = cats
            save_data(data)

        markup = types.InlineKeyboardMarkup()
        for c in cats:
            btn_edit = types.InlineKeyboardButton("[Edit] " + str(c), callback_data="editcat_" + str(c))
            btn_del = types.InlineKeyboardButton("[Delete] " + str(c), callback_data="delcat_" + str(c))
            markup.row(btn_edit, btn_del)
            
        markup.add(types.InlineKeyboardButton("+ Add New Category", callback_data="add_new_cat"))

        msg_text = "ক্যাটাগরি কন্ট্রোল প্যানেল:\nEdit করতে [Edit] বাটনে চাপুন।\nDelete করতে [Delete] বাটনে চাপুন।"
        bot.send_message(message.chat.id, msg_text, reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, "Error: " + str(e))

    except Exception as e:
        bot.send_message(message.chat.id, "ত্রুটি: " + str(e))

@bot.callback_query_handler(func=lambda call: call.data == "add_new_cat")
def callback_add_cat(call):
    if str(call.message.chat.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "নতুন ক্যাটাগরির নাম লিখে পাঠান (বাতিল করতে /cancel লিখুন):")
    bot.register_next_step_handler(msg, process_add_category)

def process_add_category(message):
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "বাতিল করা হয়েছে।")
        return
    new_cat = message.text.strip()
    data = load_data()
    cats = data.get("categories", ["BPS5", "Web Series", "Movie"])
    if new_cat in cats:
        bot.send_message(message.chat.id, "এই ক্যাটাগরিটি ইতিমধ্যে রয়েছে!")
        return
    cats.append(new_cat)
    data["categories"] = cats
    save_data(data)
    bot.send_message(message.chat.id, "নতুন ক্যাটাগরি '" + new_cat + "' সফলভাবে যোগ হয়েছে!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delcat_"))
def callback_del_cat(call):
    if str(call.message.chat.id) != str(ADMIN_ID):
        return
    target_cat = call.data.replace("delcat_", "")
    data = load_data()
    cats = data.get("categories", [])
    if target_cat in cats:
        cats.remove(target_cat)
        data["categories"] = cats
        save_data(data)
        bot.answer_callback_query(call.id, "মুছে ফেলা হয়েছে")
        bot.send_message(call.message.chat.id, "ক্যাটাগরি '" + target_cat + "' মুছে ফেলা হয়েছে!")
    else:
        bot.answer_callback_query(call.id, "ক্যাটাগরি পাওয়া যায়নি!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("editcat_"))
def callback_edit_cat(call):
    if str(call.message.chat.id) != str(ADMIN_ID):
        return
    old_cat = call.data.replace("editcat_", "")
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id, 
        "'" + old_cat + "' এর নতুন নাম কী দিতে চান? নাম লিখে পাঠান (বাতিল করতে /cancel দিন):"
    )
    bot.register_next_step_handler(msg, lambda m: process_rename_category(m, old_cat))

def process_rename_category(message, old_cat):
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "বাতিল করা হয়েছে।")
        return
    new_cat = message.text.strip()
    data = load_data()
    cats = data.get("categories", [])

    if old_cat in cats:
        idx = cats.index(old_cat)
        cats[idx] = new_cat
        data["categories"] = cats
        
        for v in data.get("videos", []):
            if v.get("category") == old_cat:
                v["category"] = new_cat
                
        save_data(data)
        bot.send_message(
            message.chat.id, 
            "ক্যাটাগরি '" + old_cat + "' পরিবর্তন করে '" + new_cat + "' করা হয়েছে!"
        )
    else:
        bot.send_message(message.chat.id, "মূল ক্যাটাগরি খুঁজে পাওয়া যায়নি।")
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.start()
    bot.infinity_polling()
