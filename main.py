import subprocess
import sys

for pkg in ["pyTelegramBotAPI", "Flask", "Flask-CORS", "requests"]:
    try:
        __import__(pkg.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import telebot
from telebot import types
from flask import Flask, jsonify, make_response, send_file, Response, request
from flask_cors import CORS
import threading
import json
import os
import time
import requests
from datetime import datetime

# ==================== কনফিগারেশন ====================
BOT_TOKEN = "8995171178:AAG8u0bCDO51BsGyFf2l14m978Pnqjzq3dU"
ADMIN_ID = "7255626228"
APP_URL = "https://enamulhossen188-ux.github.io/index.html"
DB_CHANNEL_ID = -1004330425245
RENDER_SERVER_URL = "https://my-bot-server-yeui.onrender.com"
# ====================================================

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)
CORS(app)

cached_data = None
last_cache_time = 0
CACHE_DURATION = 120
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

def upload_thumb_securely(photo_id):
    try:
        msg = bot.send_photo(DB_CHANNEL_ID, photo_id, caption="🖼 Thumb")
        perm_file_id = msg.photo[-1].file_id
        return f"{RENDER_SERVER_URL}/thumb/{perm_file_id}"
    except Exception:
        return f"{RENDER_SERVER_URL}/thumb/{photo_id}"

@app.route('/thumb/<file_id>')
def serve_thumbnail(file_id):
    if file_id in thumb_memory_cache:
        resp = Response(thumb_memory_cache[file_id], mimetype="image/jpeg")
        resp.headers['Cache-Control'] = 'public, max-age=31536000'
        return resp
    try:
        file_info = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)
        thumb_memory_cache[file_id] = file_bytes
        resp = Response(file_bytes, mimetype="image/jpeg")
        resp.headers['Cache-Control'] = 'public, max-age=31536000'
        return resp
    except Exception:
        return Response(status=404)

@app.route('/api/data', methods=['GET'])
def get_app_data():
    data = load_data(force_refresh=True)
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
        types.KeyboardButton("➕ Add Video"), types.KeyboardButton("📢 Add Coming Soon"),
        types.KeyboardButton("🔕 Delete Video"), types.KeyboardButton("📊 Total Users"),
        types.KeyboardButton("📁 Set Category"), types.KeyboardButton("🎯 Set Ads Link"),
        types.KeyboardButton("🎥 Set Welcome Video"), types.KeyboardButton("🔔 Set Video Update"),
        types.KeyboardButton("📢 BOT NOTICE")
    )
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        data = load_data()
        uid = message.chat.id
        if "users" not in data: data["users"] = []
        if uid not in data["users"]:
            data["users"].append(uid)
            save_data(data)

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
    if call.data == "btn_update":
        bot.answer_callback_query(call.id)
        data = load_data()
        bot.send_message(call.message.chat.id, f"📢 **ভিডিও আপডেট:**\n\n{data.get('update_notice', '')}")
    elif call.data == "btn_help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "💡 **ভিডিও ডাউনলোড নিয়ম:** অ্যাপে ভিডিও নির্বাচন করে দুটি বিজ্ঞাপন ১০ সেকেন্ড ভিজিট করুন, ইনবক্সে ভিডিও চলে আসবে।")

# 🔥 ২৪ ঘণ্টা নিরবচ্ছিন্নভাবে কানেক্টেড রাখার সুপার রিকানেকশন ইঞ্জিন 🔥
def run_polling_loop():
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except Exception as e:
            print("Polling reconnection:", e)
            time.sleep(2)

if __name__ == "__main__":
    t_bot = threading.Thread(target=run_polling_loop, daemon=True)
    t_bot.start()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
