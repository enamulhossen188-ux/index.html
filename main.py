import subprocess
import sys

for pkg in ["pyTelegramBotAPI", "Flask", "Flask-CORS", "requests"]:
    try:
        __import__(pkg.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import telebot
from telebot import types
from flask import Flask, jsonify, make_response, Response, request, redirect
from flask_cors import CORS
import threading
import json
import os
import time
import requests
import re
from datetime import datetime

# ==================== কনফিগারেশন ====================
BOT_TOKEN = "8995171178:AAHuypyyj8Lghg7I4F8DZFmPkZ75HLBqYDQ"
ADMIN_ID = "7255626228"
APP_URL = "https://enamulhossen188-ux.github.io/index.html"
DB_CHANNEL_ID = -1004330425245
RENDER_SERVER_URL = "https://index-html-6f0e.onrender.com"
# ====================================================

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)
CORS(app)

cached_data = None
last_cache_time = 0
CACHE_DURATION = 60
thumb_memory_cache = {}
admin_state = {}

def get_default_data():
    return {
        "users": [],
        "categories": ["BPS5", "MOVIES", "DRAMA", "SERIES", "COMING SOON"],
        "sub_categories": {},
        "ads": {"ad1": "https://google.com", "ad2": "https://google.com", "social_ad": "", "native_ad": "", "popunder_ad": ""},
        "welcome_video": "",
        "update_notice": "বর্তমানে কোনো নতুন আপডেট নেই। আমাদের সাথেই থাকুন!",
        "videos": []
    }

def get_db_file_content():
    try:
        chat = bot.get_chat(DB_CHANNEL_ID)
        pinned = chat.pinned_message
        if pinned and pinned.document:
            file_info = bot.get_file(pinned.document.file_id)
            content = bot.download_file(file_info.file_path)
            return json.loads(content.decode('utf-8'))
    except Exception as e:
        print("DB Read Error:", e)
    return None

def load_data(force_refresh=False):
    global cached_data, last_cache_time
    cur_time = time.time()
    if not force_refresh and cached_data and (cur_time - last_cache_time < CACHE_DURATION):
        return cached_data
    data = get_db_file_content()
    if data and "videos" in data:
        data.setdefault("ads", {})
        data.setdefault("sub_categories", {})
        cached_data = data
        last_cache_time = cur_time
        return cached_data
    if cached_data: return cached_data
    cached_data = get_default_data()
    return cached_data

def save_data(data):
    global cached_data, last_cache_time
    cached_data = data
    last_cache_time = time.time()
    def _async_save():
        try:
            json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
            sent_doc = bot.send_document(
                DB_CHANNEL_ID,
                ("db_backup_bot2.json", json_bytes),
                caption=f"📦 Update: {datetime.now().strftime('%d %b %Y, %I:%M:%S %p')}"
            )
            try: bot.pin_chat_message(DB_CHANNEL_ID, sent_doc.message_id, disable_notification=True)
            except Exception: pass
        except Exception as e:
            print("Save Error:", e)
    threading.Thread(target=_async_save, daemon=True).start()

def upload_thumb_securely(photo_id):
    try:
        msg = bot.send_photo(DB_CHANNEL_ID, photo_id, caption="🖼 Permanent Thumb")
        perm_file_id = msg.photo[-1].file_id
        return f"{RENDER_SERVER_URL}/thumb/{perm_file_id}"
    except Exception:
        return f"{RENDER_SERVER_URL}/thumb/{photo_id}"

@app.route('/thumb/<path:file_id>')
def serve_thumbnail(file_id):
    clean_id = file_id.strip().split('/')[-1]
    if clean_id in thumb_memory_cache:
        resp = Response(thumb_memory_cache[clean_id], mimetype='image/jpeg')
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Cache-Control'] = 'public, max-age=604800'
        return resp

    try:
        file_info = bot.get_file(clean_id)
        tg_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        r = requests.get(tg_url, timeout=12)
        if r.status_code == 200:
            thumb_memory_cache[clean_id] = r.content
            resp = Response(r.content, mimetype='image/jpeg')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Cache-Control'] = 'public, max-age=604800'
            return resp
    except Exception as e:
        print("Thumb Error:", e)

    return redirect("https://placehold.co/600x400/181920/ffffff?text=Poster", code=302)

@app.route('/api/data', methods=['GET'])
def get_app_data():
    data = load_data(force_refresh=False)
    resp = make_response(jsonify(data))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

def deliver_single_video(chat_id, target_video):
    caption_text = f"🎬 **{target_video.get('title', 'Video')}**\n\nউপভোগ করুন!"
    try:
        bot.send_video(chat_id, target_video['file_id'], caption=caption_text, supports_streaming=True, protect_content=True, parse_mode="Markdown")
        return True
    except Exception:
        try:
            bot.send_document(chat_id, target_video['file_id'], caption=caption_text)
            return True
        except Exception:
            return False

@app.route('/api/send_video', methods=['POST'])
def api_send_video():
    try:
        req_data = request.json or {}
        uid = req_data.get('user_id')
        vid = req_data.get('video_id')
        if not uid or not vid: return jsonify({'success': False}), 400
        data = load_data()
        target = next((v for v in data.get("videos", []) if str(v.get("id")) == str(vid)), None)
        if target and target.get("file_id"):
            if deliver_single_video(uid, target): return jsonify({'success': True})
        return jsonify({'success': False}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/')
def home():
    return "Bot Server Active 24/7!"

def get_action_buttons():
    fresh_url = f"{APP_URL}?v={int(datetime.now().timestamp())}"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎬 WATCH NOW", web_app=types.WebAppInfo(url=fresh_url)),
        types.InlineKeyboardButton("🔔 VIDEO UPDATE", callback_data="btn_update"),
        types.InlineKeyboardButton("💡 যেভাবে ভিডিও ডাউনলোড করবেন", callback_data="btn_help")
    )
    return markup

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🔄 Auto Sync All Thumbs"), types.KeyboardButton("➕ Add Video"),
        types.KeyboardButton("🖼 Update Thumb"), types.KeyboardButton("🔕 Delete Video"),
        types.KeyboardButton("📢 Add Coming Soon"), types.KeyboardButton("📊 Total Users"),
        types.KeyboardButton("📁 Set Category"), types.KeyboardButton("🎯 Set Ads Link"),
        types.KeyboardButton("🎥 Set Welcome Video"), types.KeyboardButton("🔔 Set Video Update"),
        types.KeyboardButton("📢 BOT NOTICE")
    )
    return markup

def get_ads_keyboard():
    data = load_data()
    ads = data.get("ads", {})
    s_status = "✅ আছে" if ads.get("social_ad") else "❌ নেই"
    n_status = "✅ আছে" if ads.get("native_ad") else "❌ নেই"
    p_status = "✅ আছে" if ads.get("popunder_ad") else "❌ নেই"

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔗 ১. Task 1 & 2 Link সেট করুন", callback_data="set_ad_tasks"),
        types.InlineKeyboardButton(f"🚀 ২. সোশ্যাল বার সেট করুন ({s_status})", callback_data="set_ad_social"),
        types.InlineKeyboardButton("🗑️ ২. সোশ্যাল বার বন্ধ করুন", callback_data="del_ad_social"),
        types.InlineKeyboardButton(f"📱 ৩. নেটিভ ব্যানার সেট করুন ({n_status})", callback_data="set_ad_native"),
        types.InlineKeyboardButton("🗑️ ৩. নেটিভ ব্যানার বন্ধ করুন", callback_data="del_ad_native"),
        types.InlineKeyboardButton(f"💥 ৪. পপআন্ডার সেট করুন ({p_status})", callback_data="set_ad_popunder"),
        types.InlineKeyboardButton("🗑️ ৪. পপআন্ডার বন্ধ করুন", callback_data="del_ad_popunder"),
        types.InlineKeyboardButton("❌ বন্ধ করুন (Close)", callback_data="close_admin_menu")
    )
    return markup

# 🔥 চ্যানেল থেকে সরাসরি চিরস্থায়ী ফটো টেনে এনে লিংক করার অটোমেটিক ইঞ্জিন 🔥
def run_auto_sync_channel(admin_chat_id):
    try:
        status_msg = bot.send_message(admin_chat_id, "⏳ **প্রাইভেট চ্যানেল থেকে ছবিগুলো স্বয়ংক্রিয়ভাবে সিঙ্ক করা হচ্ছে... অনুগ্রহ করে কিছুক্ষণ অপেক্ষা করুন।**")
        data = load_data(force_refresh=True)
        videos = data.get("videos", [])

        chat = bot.get_chat(DB_CHANNEL_ID)
        latest_msg_id = chat.pinned_message.message_id if chat.pinned_message else 15000

        recovered_count = 0
        scan_range = range(latest_msg_id, max(1, latest_msg_id - 450), -1)

        for m_id in scan_range:
            try:
                f_msg = bot.forward_message(admin_chat_id, DB_CHANNEL_ID, m_id)
                cap = (f_msg.caption or "").strip().lower()
                photo = f_msg.photo[-1] if f_msg.photo else None
                bot.delete_message(admin_chat_id, f_msg.message_id)

                if photo and cap:
                    for v in videos:
                        v_title = v.get("title", "").lower()
                        ep_match_v = re.findall(r'\d+', v_title)
                        ep_match_c = re.findall(r'\d+', cap)

                        matched = False
                        if ep_match_v and ep_match_c and ep_match_v[-1] == ep_match_c[-1]:
                            matched = True
                        elif cap in v_title or v_title in cap:
                            matched = True

                        if matched:
                            new_thumb_url = upload_thumb_securely(photo.file_id)
                            v["thumb"] = new_thumb_url
                            recovered_count += 1
                            break
            except Exception:
                continue

        save_data(data)
        bot.delete_message(admin_chat_id, status_msg.message_id)
        bot.send_message(
            admin_chat_id,
            f"🎉 **সফল হয়েছে!**\n\nমোট **{recovered_count}** টি ভিডিওর থাম্বনেইল চ্যানেল থেকে সরাসরি পার্মানেন্টলি সিঙ্ক করে নেওয়া হয়েছে। এগুলো আজীবন অক্ষত থাকবে।",
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        bot.send_message(admin_chat_id, f"❌ সিঙ্ক ত্রুটি: {str(e)}", reply_markup=get_admin_keyboard())

@bot.message_handler(commands=['admin'])
def open_admin_panel(message):
    if str(message.chat.id) != str(ADMIN_ID): return
    bot.send_message(message.chat.id, "🛠 **এডমিন প্যানেল সচল করা হয়েছে:**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")

@bot.message_handler(commands=['cancel'])
def cancel_process(message):
    chat_id = message.chat.id
    if chat_id in admin_state: del admin_state[chat_id]
    bot.send_message(chat_id, "🔄 আগের অসমাপ্ত কাজ বাতিল করা হয়েছে।", reply_markup=get_admin_keyboard() if str(chat_id) == str(ADMIN_ID) else types.ReplyKeyboardRemove())

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        data = load_data()
        uid = message.chat.id
        if "users" not in data: data["users"] = []
        if uid not in data["users"]:
            data["users"].append(uid)
            save_data(data)

        text_parts = message.text.split()
        if len(text_parts) > 1 and text_parts[1].startswith("vid_"):
            video_id = text_parts[1].replace("vid_", "")
            target_video = next((v for v in data.get("videos", []) if str(v.get("id")) == str(video_id)), None)
            if target_video and target_video.get("file_id"):
                deliver_single_video(message.chat.id, target_video)
                return

        markup = get_action_buttons()
        first_name = message.from_user.first_name or "বন্ধু"
        welcome_caption = f"**আসসালামুআলাইকুম {first_name} 🥰**\n\nআমাদের বট ২৪ ঘণ্টা সচল। নাটক দেখতে ও ডাউনলোড করতে নিচের **WATCH NOW** বাটনে ক্লিক করুন।"

        if data.get("welcome_video"):
            try: bot.send_video(uid, data["welcome_video"], caption=welcome_caption, reply_markup=markup, parse_mode="Markdown")
            except Exception: bot.send_message(uid, welcome_caption, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(uid, welcome_caption, reply_markup=markup, parse_mode="Markdown")

        if str(uid) == str(ADMIN_ID):
            bot.send_message(uid, "🛠️ **এডমিন প্যানেল সচল করা হয়েছে:**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    except Exception as e:
        print("Welcome error:", e)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    if call.data == "btn_update":
        bot.answer_callback_query(call.id)
        data = load_data()
        bot.send_message(chat_id, f"📢 **ভিডিও আপডেট:**\n\n{data.get('update_notice', 'কোনো আপডেট নেই।')}")
        return
    elif call.data == "btn_help":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "💡 **ভিডিও ডাউনলোড নিয়ম:** অ্যাপে ভিডিও নির্বাচন করে দুটি টাস্ক ১০ সেকেন্ড করে সম্পন্ন করুন, ইনবক্সে ভিডিও চলে আসবে।")
        return

    if str(chat_id) != str(ADMIN_ID): return

    if call.data == "close_admin_menu":
        bot.delete_message(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    elif call.data in ["set_ad_popunder", "set_popunder_ad"]:
        admin_state[chat_id] = {'step': 'set_popunder_ad'}
        bot.send_message(chat_id, "💥 **পপআন্ডার কোড বা লিংকটি পাঠান:**\n(বাতিল করতে /cancel লিখুন)")
        bot.answer_callback_query(call.id)
        return
    elif call.data in ["del_ad_popunder", "del_popunder_ad"]:
        data = load_data(force_refresh=True)
        data.setdefault("ads", {})["popunder_ad"] = ""
        save_data(data)
        bot.answer_callback_query(call.id, "🗑️ পপআন্ডার বন্ধ করা হয়েছে!", show_alert=True)
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=get_ads_keyboard())
        return

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_admin_inputs(message):
    chat_id = message.chat.id
    if str(chat_id) != str(ADMIN_ID): return

    if message.text == "🔄 Auto Sync All Thumbs":
        threading.Thread(target=run_auto_sync_channel, args=(chat_id,), daemon=True).start()
        return
    elif message.text == "➕ Add Video":
        admin_state[chat_id] = {'step': 'category'}
        data = load_data(force_refresh=True)
        cats = data.get("categories", ["BPS5", "MOVIES", "DRAMA", "SERIES"])
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for i in range(0, len(cats), 2): markup.row(*[types.KeyboardButton(c) for c in cats[i:i+2]])
        bot.send_message(chat_id, "📁 **ভিডিওর ক্যাটাগরি বেছে নিন:**", reply_markup=markup)
        return
    elif message.text == "🎯 Set Ads Link":
        bot.send_message(chat_id, "🎯 **বিজ্ঞাপন সেটিংস ও নিয়ন্ত্রণ:**", reply_markup=get_ads_keyboard())
        return

    if chat_id not in admin_state: return
    step = admin_state[chat_id].get('step')

    if step == 'set_popunder_ad' and message.text:
        data = load_data(force_refresh=True)
        data.setdefault("ads", {})["popunder_ad"] = message.text.strip()
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **পপআন্ডার সফলভাবে আপডেট হয়েছে!**", reply_markup=get_admin_keyboard())
        return
    elif step == 'category' and message.text:
        admin_state[chat_id]['category'] = message.text.strip()
        admin_state[chat_id]['step'] = 'title'
        bot.send_message(chat_id, "🎬 **ভিডিওর নাম (Title) লিখুন:**", reply_markup=types.ReplyKeyboardRemove())
        return
    elif step == 'title' and message.text:
        admin_state[chat_id]['title'] = message.text.strip()
        admin_state[chat_id]['step'] = 'thumb'
        bot.send_message(chat_id, "🖼 **থাম্বনেইল ছবি পাঠান:**")
        return
    elif step == 'thumb' and (message.photo or message.text):
        thumb_url = upload_thumb_securely(message.photo[-1].file_id) if message.photo else message.text.strip()
        admin_state[chat_id]['thumb'] = thumb_url
        admin_state[chat_id]['step'] = 'video'
        bot.send_message(chat_id, "📥 **ভিডিও ফাইলটি পাঠান:**")
        return
    elif step == 'video' and (message.video or message.document):
        incoming_file_id = message.video.file_id if message.video else message.document.file_id
        data = load_data(force_refresh=True)
        new_video = {
            "id": int(time.time()),
            "category": admin_state[chat_id]['category'],
            "title": admin_state[chat_id]['title'],
            "thumb": admin_state[chat_id].get('thumb', ''),
            "file_id": incoming_file_id,
            "date": datetime.now().strftime("%b %d, %Y"),
            "time": datetime.now().strftime("%I:%M %p")
        }
        data.setdefault("videos", []).insert(0, new_video)
        save_data(data)
        del admin_state[chat_id]
        bot.reply_to(message, "🎉 **ভিডিও আপলোড সম্পন্ন!**", reply_markup=get_admin_keyboard())
        return

def internal_self_pinger():
    time.sleep(15)
    while True:
        try:
            requests.get(f"{RENDER_SERVER_URL}/", timeout=10)
        except Exception: pass
        time.sleep(240)

def run_polling_loop():
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=internal_self_pinger, daemon=True).start()
    threading.Thread(target=run_polling_loop, daemon=True).start()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
