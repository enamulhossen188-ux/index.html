import subprocess
import sys

for pkg in ["pyTelegramBotAPI", "Flask", "Flask-CORS", "requests"]:
    try:
        __import__(pkg.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import telebot
from telebot import types
from flask import Flask, jsonify, make_response, Response, request, redirect, send_file
from flask_cors import CORS
import threading
import json
import os
import time
import base64
import requests
import re
from datetime import datetime

# ==================== কনফিগারেশন ====================
BOT_TOKEN = "8995171178:AAFxdUeC4bR7L7AZn4_tLqU38t4burawv8c"
ADMIN_ID = "7255626228"
DB_CHANNEL_ID = -1004330425245
RENDER_SERVER_URL = "https://bp-bot-v2.onrender.com"
APP_URL = f"{RENDER_SERVER_URL}/app"

# থাম্বনেইল ব্যাকআপের জন্য GitHub কনফিগারেশন
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER = "enamulhossen188-ux"
GITHUB_REPO = "index.html"
GITHUB_BRANCH = "main"
# ====================================================

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)
CORS(app)

cached_data = None
last_cache_time = 0
CACHE_DURATION = 180
thumb_memory_cache = {}
admin_state = {}
github_lock = threading.Lock()
db_save_lock = threading.Lock()
last_local_save_time = 0


def extract_single_url(raw_text):
    if not raw_text:
        return "https://www.google.com"
    first_part = str(raw_text).split(",")[0].strip()
    match = re.search(r'https?://[^\s"\'<>]+', first_part)
    return match.group(0) if match else "https://www.google.com"


def push_file_to_github(file_path, content_bytes, commit_msg):
    if not GITHUB_TOKEN:
        return None
    with github_lock:
        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{file_path}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        sha = None
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                sha = r.json().get("sha")
        except Exception:
            pass

        payload = {
            "message": commit_msg,
            "content": base64.b64encode(content_bytes).decode("utf-8"),
            "branch": GITHUB_BRANCH
        }
        if sha:
            payload["sha"] = sha

        try:
            res = requests.put(url, headers=headers, json=payload, timeout=15)
            if res.status_code in [200, 201]:
                return f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}/{file_path}"
        except Exception as e:
            print("GitHub Push Error:", e)
    return None


def get_default_data():
    return {
        "users": [],
        "categories": ["BPS5", "MOVIES", "DRAMA", "SERIES", "COMING SOON"],
        "sub_categories": {},
        "ads": {
            "ad1": "https://www.google.com",
            "ad2": "https://www.google.com",
            "ad3": "https://www.google.com",
            "ad4": "https://www.google.com",
            "social_ad": "",
            "native_ad": "",
            "popunder_ad": ""
        },
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
    if cached_data and (cur_time - last_local_save_time < 60):
        return cached_data
    if not force_refresh and cached_data and (cur_time - last_cache_time < CACHE_DURATION):
        return cached_data
    with db_save_lock:
        data = get_db_file_content()
    if data and "videos" in data:
        data.setdefault("ads", {})
        data.setdefault("sub_categories", {})
        for k in ["ad1", "ad2", "ad3", "ad4"]:
            data["ads"][k] = extract_single_url(data["ads"].get(k, ""))
        cached_data = data
        last_cache_time = cur_time
        return cached_data
    if cached_data:
        return cached_data
    cached_data = get_default_data()
    return cached_data


def save_data(data):
    global cached_data, last_cache_time, last_local_save_time
    cached_data = data
    last_cache_time = time.time()
    last_local_save_time = time.time()

    def _async_save():
        with db_save_lock:
            try:
                json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
                sent_doc = bot.send_document(
                    DB_CHANNEL_ID,
                    ("db_backup_bot2.json", json_bytes),
                    caption=f"📦 Update: {datetime.now().strftime('%d %b %Y, %I:%M:%S %p')}",
                    protect_content=True
                )
                try:
                    bot.pin_chat_message(DB_CHANNEL_ID, sent_doc.message_id, disable_notification=True)
                except Exception:
                    pass
            except Exception as e:
                print("Save Error:", e)

    threading.Thread(target=_async_save, daemon=True).start()


def upload_thumb_securely(photo_id):
    try:
        msg = bot.send_photo(DB_CHANNEL_ID, photo_id, caption="🖼 Permanent Thumb", protect_content=True)
        perm_file_id = msg.photo[1].file_id if len(msg.photo) > 1 else msg.photo[-1].file_id
    except Exception:
        perm_file_id = photo_id

    try:
        file_info = bot.get_file(perm_file_id)
        img_bytes = bot.download_file(file_info.file_path)
        file_name = f"thumbs/img_{int(time.time() * 1000)}.jpg"
        gh_url = push_file_to_github(file_name, img_bytes, f"Upload {file_name}")
        if gh_url:
            return gh_url
    except Exception as e:
        print("Thumb Upload Error:", e)

    return f"{RENDER_SERVER_URL}/thumb/{perm_file_id}"


@app.route('/app')
def serve_mini_app():
    """সরাসরি Render সার্ভার থেকে কোনো দেরি ছাড়া মিনি অ্যাপ ওপেন করবে"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        resp = make_response(html_content)
        resp.headers['Content-Type'] = 'text/html; charset=utf-8'
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp
    except Exception as e:
        return f"App Load Error: {str(e)}", 500


@app.route('/thumb/<path:file_id>')
def serve_thumbnail(file_id):
    clean_id = file_id.strip().split('/')[-1]
    if clean_id in thumb_memory_cache:
        resp = Response(thumb_memory_cache[clean_id], mimetype='image/jpeg')
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Cache-Control'] = 'public, max-age=2592000'
        return resp

    try:
        file_info = bot.get_file(clean_id)
        tg_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        r = requests.get(tg_url, timeout=12)
        if r.status_code == 200:
            if len(thumb_memory_cache) > 150:
                thumb_memory_cache.clear()
            thumb_memory_cache[clean_id] = r.content
            resp = Response(r.content, mimetype='image/jpeg')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Cache-Control'] = 'public, max-age=2592000'
            return resp
    except Exception as e:
        print("Thumb Error:", e)

    return redirect("https://placehold.co/600x400/181920/ffffff?text=Poster", code=302)


@app.route('/api/data', methods=['GET'])
def get_app_data():
    data = load_data(force_refresh=False)
    ads = data.get("ads", {})
    clean_ads = {
        "ad1": extract_single_url(ads.get("ad1", "")),
        "ad2": extract_single_url(ads.get("ad2", "")),
        "ad3": extract_single_url(ads.get("ad3", "")),
        "ad4": extract_single_url(ads.get("ad4", "")),
        "social_ad": ads.get("social_ad", ""),
        "native_ad": ads.get("native_ad", ""),
        "popunder_ad": ads.get("popunder_ad", "")
    }
    light_data = {
        "categories": data.get("categories", []),
        "sub_categories": data.get("sub_categories", {}),
        "ads": clean_ads,
        "update_notice": data.get("update_notice", ""),
        "videos": data.get("videos", [])
    }
    resp = make_response(jsonify(light_data))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


def deliver_single_video(chat_id, target_video):
    caption_text = f"🎬 **{target_video.get('title', 'Video')}**\n\nউপভোগ করুন!"
    try:
        bot.send_video(chat_id, target_video['file_id'], caption=caption_text, supports_streaming=True, protect_content=True, parse_mode="Markdown")
        return True
    except Exception:
        try:
            bot.send_document(chat_id, target_video['file_id'], caption=caption_text, protect_content=True)
            return True
        except Exception:
            return False


@app.route('/api/send_video', methods=['POST'])
def api_send_video():
    try:
        req_data = request.json or {}
        uid = req_data.get('user_id')
        vid = req_data.get('video_id')
        if not uid or not vid:
            return jsonify({'success': False}), 400
        data = load_data()
        target = next((v for v in data.get("videos", []) if str(v.get("id")) == str(vid)), None)
        if target and target.get("file_id"):
            if deliver_single_video(uid, target):
                return jsonify({'success': True})
        return jsonify({'success': False}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/')
def home():
    return "Bot Server Active 24/7 (Direct Render Fast Mode)!"


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
        types.KeyboardButton("➕ Add Video"), types.KeyboardButton("🖼 Update Thumb"),
        types.KeyboardButton("🔕 Delete Video"), types.KeyboardButton("📢 Add Coming Soon"),
        types.KeyboardButton("📊 Total Users"), types.KeyboardButton("📁 Set Category"),
        types.KeyboardButton("🎯 Set Ads Link"), types.KeyboardButton("🎥 Set Welcome Video"),
        types.KeyboardButton("🔔 Set Video Update"), types.KeyboardButton("📢 BOT NOTICE")
    )
    return markup


def get_ads_keyboard():
    data = load_data()
    ads = data.get("ads", {})
    has_custom_task = any("google.com" not in str(ads.get(k, "")) for k in ["ad1", "ad2", "ad3", "ad4"])
    t_status = "🔗 সেট করা আছে" if has_custom_task else "🌐 গুগল (ডিফল্ট)"

    s_status = "✅ আছে" if ads.get("social_ad") else "❌ নেই"
    n_status = "✅ আছে" if ads.get("native_ad") else "❌ নেই"
    p_status = "✅ আছে" if ads.get("popunder_ad") else "❌ নেই"

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"🔗 ১. Task 1–4 Link সেট করুন ({t_status})", callback_data="set_ad_tasks"),
        types.InlineKeyboardButton("🗑️ ১. সব Task Link রিসেট (গুগল করুন)", callback_data="reset_ad_tasks"),
        types.InlineKeyboardButton(f"🚀 ২. সোশ্যাল বার সেট করুন ({s_status})", callback_data="set_ad_social"),
        types.InlineKeyboardButton("🗑️ ২. সোশ্যাল বার বন্ধ করুন", callback_data="del_ad_social"),
        types.InlineKeyboardButton(f"📱 ৩. নেটিভ ব্যানার সেট করুন ({n_status})", callback_data="set_ad_native"),
        types.InlineKeyboardButton("🗑️ ৩. নেটিভ ব্যানার বন্ধ করুন", callback_data="del_ad_native"),
        types.InlineKeyboardButton(f"💥 ৪. পপআন্ডার সেট করুন ({p_status})", callback_data="set_ad_popunder"),
        types.InlineKeyboardButton("🗑️ ৪. পপআন্ডার বন্ধ করুন", callback_data="del_ad_popunder"),
        types.InlineKeyboardButton("❌ বন্ধ করুন (Close)", callback_data="close_admin_menu")
    )
    return markup


def get_category_keyboard():
    data = load_data(force_refresh=True)
    cats = data.get("categories", ["BPS5", "MOVIES", "DRAMA", "SERIES", "COMING SOON"])
    markup = types.InlineKeyboardMarkup()
    for c in cats:
        markup.add(types.InlineKeyboardButton(f"🗑 Delete: {c}", callback_data=f"delcat_{c}"))
    markup.add(types.InlineKeyboardButton("➕ Add New Category", callback_data="add_new_category"))
    markup.add(types.InlineKeyboardButton("❌ বন্ধ করুন (Close)", callback_data="close_admin_menu"))
    return markup


def filter_videos_by_category(videos, cat_name):
    if not cat_name or cat_name == "ALL":
        return videos
    target = cat_name.strip().upper()
    filtered = []
    for v in videos:
        item_cat = str(v.get("category", "")).strip().upper()
        item_title = str(v.get("title", "")).strip().lower()
        if target == "BPS5":
            if item_cat == "BPS5" or "bachelor point" in item_title or "ব্যাচেলর" in item_title:
                filtered.append(v)
        elif target == "COMING SOON" or "COMING" in target:
            if v.get("is_coming_soon") or "COMING" in item_cat:
                filtered.append(v)
        else:
            if item_cat == target:
                filtered.append(v)
    return filtered


def get_section_category_keyboard(mode):
    data = load_data(force_refresh=True)
    videos = data.get("videos", [])
    cats = data.get("categories", ["BPS5", "MOVIES", "DRAMA", "SERIES", "COMING SOON"])

    markup = types.InlineKeyboardMarkup(row_width=2)
    cat_buttons = []
    for c in cats:
        count = len(filter_videos_by_category(videos, c))
        cat_buttons.append(types.InlineKeyboardButton(f"📁 {c} ({count})", callback_data=f"{mode}cat|{c}|0"))

    for i in range(0, len(cat_buttons), 2):
        markup.row(*cat_buttons[i:i + 2])

    markup.add(types.InlineKeyboardButton(f"📋 সব ভিডিও একসাথে ({len(videos)})", callback_data=f"{mode}cat|ALL|0"))
    markup.add(types.InlineKeyboardButton("❌ বন্ধ করুন (Close)", callback_data="close_admin_menu"))
    return markup


def format_short_btn_title(title, max_len=36):
    t = str(title or "Video").strip()
    if len(t) <= max_len:
        return t
    return t[:14] + "..." + t[-(max_len - 17):]


def get_thumb_view_data(cat_name="ALL", page=0):
    data = load_data(force_refresh=True)
    all_videos = data.get("videos", [])
    videos = filter_videos_by_category(all_videos, cat_name)
    if not videos:
        return None, None

    per_page = 8
    total_pages = (len(videos) + per_page - 1) // per_page
    if page >= total_pages:
        page = max(0, total_pages - 1)
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_videos = videos[start_idx:end_idx]

    label = "সব ভিডিও" if cat_name == "ALL" else cat_name
    text_msg = f"🖼 **থাম্বনেইল পরিবর্তন [{label}] (পেজ: {page + 1}/{total_pages}):**\n\n"
    markup = types.InlineKeyboardMarkup()

    for idx, v in enumerate(current_videos, start=start_idx + 1):
        full_title = v.get('title', 'Video')
        text_msg += f"**{idx}.** {full_title}\n"
        btn_label = f"🖼 {idx}. {format_short_btn_title(full_title)}"
        markup.add(types.InlineKeyboardButton(btn_label, callback_data=f"setthumb|{v.get('id')}|{cat_name}|{page}"))

    text_msg += "\n👇 যে ভিডিওর থাম্বনেইল বদলাতে চান তার নম্বরে চাপ দিন:"

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"thumbcat|{cat_name}|{page - 1}"))
    if end_idx < len(videos):
        nav_buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"thumbcat|{cat_name}|{page + 1}"))
    if nav_buttons:
        markup.row(*nav_buttons)

    markup.add(types.InlineKeyboardButton("🔙 ক্যাটাগরি তালিকায় ফিরুন", callback_data="back_to_thumb_cats"))
    markup.add(types.InlineKeyboardButton("❌ বন্ধ করুন (Close)", callback_data="close_admin_menu"))
    return text_msg, markup


def get_delete_view_data(cat_name="ALL", page=0):
    data = load_data(force_refresh=True)
    all_videos = data.get("videos", [])
    videos = filter_videos_by_category(all_videos, cat_name)
    if not videos:
        return None, None

    per_page = 8
    total_pages = (len(videos) + per_page - 1) // per_page
    if page >= total_pages:
        page = max(0, total_pages - 1)
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_videos = videos[start_idx:end_idx]

    label = "সব ভিডিও" if cat_name == "ALL" else cat_name
    text_msg = f"🗑️ **ভিডিও ডিলিট মেনু [{label}] (পেজ: {page + 1}/{total_pages}):**\n\n"
    markup = types.InlineKeyboardMarkup()

    for idx, v in enumerate(current_videos, start=start_idx + 1):
        full_title = v.get('title', 'Video')
        is_cs = v.get("is_coming_soon") or v.get("category") == "COMING SOON"
        tag = " [📢 COMING SOON]" if is_cs else ""
        text_msg += f"**{idx}.** {full_title}{tag}\n"
        btn_label = f"🗑️ {idx}. {format_short_btn_title(full_title)}"
        markup.add(types.InlineKeyboardButton(btn_label, callback_data=f"delvid|{v.get('id')}|{cat_name}|{page}"))

    text_msg += "\n👇 যে ভিডিওটি ডিলিট করতে চান তার নম্বরে চাপ দিন:"

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"delcat|{cat_name}|{page - 1}"))
    if end_idx < len(videos):
        nav_buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"delcat|{cat_name}|{page + 1}"))
    if nav_buttons:
        markup.row(*nav_buttons)

    markup.add(types.InlineKeyboardButton("🔙 ক্যাটাগরি তালিকায় ফিরুন", callback_data="back_to_del_cats"))
    markup.add(types.InlineKeyboardButton("❌ বন্ধ করুন (Close)", callback_data="close_admin_menu"))
    return text_msg, markup


@bot.message_handler(commands=['admin'])
def open_admin_panel(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ **আপনি এই বটের মালিক নন!**")
        return
    bot.send_message(message.chat.id, "🛠 **এডমিন প্যানেল সচল করা হয়েছে:**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")


@bot.message_handler(commands=['cancel'])
def cancel_process(message):
    chat_id = message.chat.id
    if str(chat_id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ **আপনি এই বটের মালিক নন!**")
        return
    if chat_id in admin_state:
        del admin_state[chat_id]
    bot.send_message(chat_id, "🔄 আগের অসমাপ্ত কাজ বাতিল করা হয়েছে।", reply_markup=get_admin_keyboard())


@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        data = load_data()
        uid = message.chat.id
        if "users" not in data:
            data["users"] = []
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
            try:
                bot.send_video(uid, data["welcome_video"], caption=welcome_caption, reply_markup=markup, parse_mode="Markdown", protect_content=True)
            except Exception:
                bot.send_message(uid, welcome_caption, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(uid, welcome_caption, reply_markup=markup, parse_mode="Markdown")

        if str(uid) == str(ADMIN_ID):
            bot.send_message(uid, "🛠️ **এডমিন প্যানেল সচল করা হয়েছে:**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    except Exception as e:
        print("Welcome error:", e)


def run_broadcast_worker(admin_chat_id, media_type, file_id, caption_text, with_btn, user_list):
    notice_markup = None
    if with_btn:
        fresh_url = f"{APP_URL}?v={int(datetime.now().timestamp())}"
        notice_markup = types.InlineKeyboardMarkup()
        notice_markup.add(types.InlineKeyboardButton("🎬 WATCH NOW", web_app=types.WebAppInfo(url=fresh_url)))

    sent = 0
    for uid in user_list:
        try:
            if media_type == 'video':
                bot.send_video(uid, file_id, caption=caption_text, reply_markup=notice_markup, protect_content=True)
            elif media_type == 'photo':
                bot.send_photo(uid, file_id, caption=caption_text, reply_markup=notice_markup, protect_content=True)
            else:
                bot.send_message(uid, caption_text, reply_markup=notice_markup)
            sent += 1
            time.sleep(0.04)
        except Exception:
            pass
    bot.send_message(admin_chat_id, f"✅ ব্যাকগ্রাউন্ডে মোট **{sent}** জনের কাছে নোটিশ পাঠানো সম্পন্ন!")


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
        bot.send_message(chat_id, "💡 **ভিডিও ডাউনলোড নিয়ম:** অ্যাপে ভিডিও নির্বাচন করে ৪টি টাস্ক ১০ সেকেন্ড করে সম্পন্ন করুন, ইনবক্সে ভিডিও চলে আসবে।")
        return

    if str(chat_id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ আপনি এই বটের মালিক নন!", show_alert=True)
        return

    if call.data in ["bc_with_btn", "bc_without_btn"]:
        if chat_id in admin_state and admin_state[chat_id].get('step') == 'confirm_broadcast':
            with_btn = (call.data == "bc_with_btn")
            st = admin_state[chat_id]
            media_type = st.get('media_type')
            file_id = st.get('file_id')
            caption_text = st.get('caption')
            del admin_state[chat_id]

            data = load_data()
            user_list = data.get("users", [])
            bot.delete_message(chat_id, call.message.message_id)
            btn_txt = "বাটন সহ" if with_btn else "বাটন ছাড়া"
            bot.send_message(chat_id, f"⏳ **{btn_txt} {len(user_list)} জন ইউজারের কাছে নোটিশ পাঠানো হচ্ছে... বট সম্পূর্ণ সচল থাকবে।**", reply_markup=get_admin_keyboard())

            threading.Thread(
                target=run_broadcast_worker,
                args=(chat_id, media_type, file_id, caption_text, with_btn, user_list),
                daemon=True
            ).start()
        return

    if call.data == "close_admin_menu":
        bot.delete_message(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    elif call.data == "set_ad_tasks":
        admin_state[chat_id] = {'step': 'ad_1'}
        bot.send_message(chat_id, "🔗 **Task 1 এর এড লিংক পাঠান:**\n(বাতিল করতে /cancel লিখুন)")
        bot.answer_callback_query(call.id)
        return
    elif call.data == "reset_ad_tasks":
        data = load_data(force_refresh=True)
        ads = data.setdefault("ads", {})
        ads["ad1"] = "https://www.google.com"
        ads["ad2"] = "https://www.google.com"
        ads["ad3"] = "https://www.google.com"
        ads["ad4"] = "https://www.google.com"
        save_data(data)
        bot.answer_callback_query(call.id, "🌐 ৪টি টাস্কই গুগলে রিসেট করা হয়েছে!", show_alert=True)
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=get_ads_keyboard())
        return
    elif call.data == "set_ad_social":
        admin_state[chat_id] = {'step': 'set_social_ad'}
        bot.send_message(chat_id, "🚀 **সোশ্যাল বার স্ক্রিপ্ট বা ডিরেক্ট লিংক পাঠান:**\n(বাতিল করতে /cancel লিখুন)")
        bot.answer_callback_query(call.id)
        return
    elif call.data == "del_ad_social":
        data = load_data(force_refresh=True)
        data.setdefault("ads", {})["social_ad"] = ""
        save_data(data)
        bot.answer_callback_query(call.id, "🗑️ সোশ্যাল বার বন্ধ করা হয়েছে!", show_alert=True)
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=get_ads_keyboard())
        return
    elif call.data == "set_ad_native":
        admin_state[chat_id] = {'step': 'set_native_ad'}
        bot.send_message(chat_id, "📱 **নেটিভ ব্যানার কোড বা লিংক পাঠান:**\n(বাতিল করতে /cancel লিখুন)")
        bot.answer_callback_query(call.id)
        return
    elif call.data == "del_ad_native":
        data = load_data(force_refresh=True)
        data.setdefault("ads", {})["native_ad"] = ""
        save_data(data)
        bot.answer_callback_query(call.id, "🗑️ নেটিভ ব্যানার বন্ধ করা হয়েছে!", show_alert=True)
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=get_ads_keyboard())
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

    if call.data == "back_to_thumb_cats":
        kb = get_section_category_keyboard("thumb")
        bot.edit_message_text("🖼 **থাম্বনেইল পরিবর্তনের জন্য ক্যাটাগরি বেছে নিন:**", chat_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("thumbcat|"):
        parts = call.data.split("|")
        cat_name = parts[1]
        page = int(parts[2])
        txt, kb = get_thumb_view_data(cat_name, page)
        if kb:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "❌ এই ক্যাটাগরিতে কোনো ভিডিও নেই!", show_alert=True)
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("setthumb|"):
        parts = call.data.split("|")
        vid_id = parts[1]
        admin_state[chat_id] = {'step': 'upload_new_thumb', 'vid_id': vid_id}
        bot.send_message(chat_id, "📷 **এই ভিডিওটির জন্য আসল থাম্বনেইল ছবিটি পাঠিয়ে দিন:**\n(বাতিল করতে /cancel লিখুন)")
        bot.answer_callback_query(call.id)
        return

    if call.data == "back_to_del_cats":
        kb = get_section_category_keyboard("del")
        bot.edit_message_text("🗑️ **ভিডিও ডিলিট করার জন্য ক্যাটাগরি বেছে নিন:**", chat_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("delcat|"):
        parts = call.data.split("|")
        cat_name = parts[1]
        page = int(parts[2])
        txt, kb = get_delete_view_data(cat_name, page)
        if kb:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "❌ এই ক্যাটাগরিতে কোনো ভিডিও নেই!", show_alert=True)
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("delvid|"):
        parts = call.data.split("|")
        del_id = parts[1]
        cat_name = parts[2]
        page = int(parts[3]) if len(parts) > 3 else 0
        data = load_data(force_refresh=True)
        data["videos"] = [v for v in data.get("videos", []) if str(v.get('id')) != str(del_id)]
        save_data(data)
        bot.answer_callback_query(call.id, "✅ সফলভাবে ডিলিট করা হয়েছে!", show_alert=True)
        txt, kb = get_delete_view_data(cat_name, page)
        if kb:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        else:
            kb_cats = get_section_category_keyboard("del")
            bot.edit_message_text("✅ এই ক্যাটাগরির সব ভিডিও ডিলিট হয়েছে! অন্য ক্যাটাগরি বেছে নিন:", chat_id, call.message.message_id, reply_markup=kb_cats)
        return

    if call.data.startswith("delcat_"):
        cat_to_del = call.data.replace("delcat_", "")
        data = load_data(force_refresh=True)
        cats = data.get("categories", [])
        if cat_to_del in cats:
            cats.remove(cat_to_del)
            data["categories"] = cats
            save_data(data)
            bot.answer_callback_query(call.id, f"✅ '{cat_to_del}' মুছে ফেলা হয়েছে!", show_alert=True)
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=get_category_keyboard())
        return
    if call.data == "add_new_category":
        admin_state[chat_id] = {'step': 'add_single_category'}
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "📁 **যে নতুন ক্যাটাগরি যুক্ত করতে চান তার নাম লিখে পাঠান:**\n(বাতিল করতে /cancel লিখুন)")
        return


@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_admin_inputs(message):
    chat_id = message.chat.id

    admin_buttons = [
        "➕ Add Video", "🖼 Update Thumb", "🔕 Delete Video",
        "📢 Add Coming Soon", "📊 Total Users", "📁 Set Category", "🎯 Set Ads Link",
        "🎥 Set Welcome Video", "🔔 Set Video Update", "📢 BOT NOTICE"
    ]
    if message.text in admin_buttons and str(chat_id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ **আপনি এই বটের মালিক নন!**")
        return

    if str(chat_id) != str(ADMIN_ID):
        return

    if message.text == "➕ Add Video":
        admin_state[chat_id] = {'step': 'category'}
        data = load_data(force_refresh=True)
        cats = data.get("categories", ["BPS5", "MOVIES", "DRAMA", "SERIES"])
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for i in range(0, len(cats), 2):
            markup.row(*[types.KeyboardButton(c) for c in cats[i:i + 2]])
        bot.send_message(chat_id, "📁 **ভিডিওর ক্যাটাগরি বেছে নিন:**", reply_markup=markup)
        return
    elif message.text == "🖼 Update Thumb":
        data = load_data(force_refresh=True)
        if not data.get("videos"):
            bot.send_message(chat_id, "❌ কোনো ভিডিও পাওয়া যায়নি!", reply_markup=get_admin_keyboard())
            return
        kb = get_section_category_keyboard("thumb")
        bot.send_message(chat_id, "🖼 **থাম্বনেইল পরিবর্তনের জন্য ক্যাটাগরি বেছে নিন:**", reply_markup=kb, parse_mode="Markdown")
        return
    elif message.text == "🔕 Delete Video":
        data = load_data(force_refresh=True)
        if not data.get("videos"):
            bot.send_message(chat_id, "❌ কোনো ভিডিও পাওয়া যায়নি!", reply_markup=get_admin_keyboard())
            return
        kb = get_section_category_keyboard("del")
        bot.send_message(chat_id, "🗑️ **ভিডিও ডিলিট করার জন্য ক্যাটাগরি বেছে নিন:**", reply_markup=kb, parse_mode="Markdown")
        return
    elif message.text == "📢 Add Coming Soon":
        admin_state[chat_id] = {'step': 'cs_title', 'category': 'COMING SOON', 'is_coming_soon': True}
        bot.send_message(chat_id, "🎬 **কামিং সুন ভিডিওর টাইটেল লিখুন:**", reply_markup=types.ReplyKeyboardRemove())
        return
    elif message.text == "📊 Total Users":
        data = load_data()
        user_list = data.get("users", [])
        bot.send_message(chat_id, f"📊 মোট সক্রিয় ইউজার: **{len(user_list)}** জন\nমোট ভিডিও: **{len(data.get('videos', []))}** টি")
        return
    elif message.text == "📁 Set Category":
        bot.send_message(chat_id, "📁 **ক্যাটাগরি ম্যানেজমেন্ট:**", reply_markup=get_category_keyboard())
        return
    elif message.text == "🎯 Set Ads Link":
        bot.send_message(chat_id, "🎯 **বিজ্ঞাপন সেটিংস ও নিয়ন্ত্রণ:**", reply_markup=get_ads_keyboard())
        return
    elif message.text == "🎥 Set Welcome Video":
        admin_state[chat_id] = {'step': 'welcome_video'}
        bot.send_message(chat_id, "🎥 **স্টার্টের ওয়েলকাম ভিডিওটি পাঠান:**")
        return
    elif message.text == "🔔 Set Video Update":
        admin_state[chat_id] = {'step': 'set_video_update'}
        data = load_data()
        bot.send_message(chat_id, f"🔔 **নোটিশ লিখে পাঠান:**\n`{data.get('update_notice', '')}`", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
        return
    elif message.text == "📢 BOT NOTICE":
        admin_state[chat_id] = {'step': 'notice_input'}
        bot.send_message(chat_id, "📢 **নোটিশের জন্য ভিডিও, ছবি অথবা শুধু মেসেজ লিখে পাঠান:**\n(বাতিল করতে /cancel লিখুন)", reply_markup=types.ReplyKeyboardRemove())
        return

    if chat_id not in admin_state:
        return
    step = admin_state[chat_id].get('step')

    if step == 'upload_new_thumb' and (message.photo or message.text):
        vid_id = admin_state[chat_id].get('vid_id')
        thumb_url = upload_thumb_securely(message.photo[-1].file_id) if message.photo else message.text.strip()
        data = load_data(force_refresh=True)
        updated = False
        for v in data.get("videos", []):
            if str(v.get("id")) == str(vid_id):
                v["thumb"] = thumb_url
                updated = True
                break
        if updated:
            save_data(data)
            del admin_state[chat_id]
            bot.reply_to(message, "🎉 **থাম্বনেইল সফলভাবে আপডেট হয়েছে!**", reply_markup=get_admin_keyboard())
        else:
            bot.reply_to(message, "❌ ভিডিওটি পাওয়া যায়নি!", reply_markup=get_admin_keyboard())
        return

    if step == 'notice_input':
        m_type = 'text'
        f_id = None
        cap = ""

        if message.video:
            m_type = 'video'
            f_id = message.video.file_id
            cap = message.caption or ""
        elif message.photo:
            m_type = 'photo'
            f_id = message.photo[-1].file_id
            cap = message.caption or ""
        elif message.text:
            m_type = 'text'
            cap = message.text

        admin_state[chat_id] = {
            'step': 'confirm_broadcast',
            'media_type': m_type,
            'file_id': f_id,
            'caption': cap
        }

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("✅ 'WATCH NOW' বাটন সহ পাঠান", callback_data="bc_with_btn"),
            types.InlineKeyboardButton("🚫 কোনো বাটন ছাড়া সরাসরি পাঠান", callback_data="bc_without_btn")
        )
        bot.send_message(chat_id, "🎯 **নোটিশটি কীভাবে পাঠাতে চান বেছে নিন:**", reply_markup=markup)
        return

    if step == 'ad_1' and message.text:
        admin_state[chat_id]['ad1'] = extract_single_url(message.text)
        admin_state[chat_id]['step'] = 'ad_2'
        bot.send_message(chat_id, "🎯 **এবার Task 2 এর লিংক পাঠান:**")
        return
    elif step == 'ad_2' and message.text:
        admin_state[chat_id]['ad2'] = extract_single_url(message.text)
        admin_state[chat_id]['step'] = 'ad_3'
        bot.send_message(chat_id, "🎯 **এবার Task 3 এর লিংক পাঠান:**")
        return
    elif step == 'ad_3' and message.text:
        admin_state[chat_id]['ad3'] = extract_single_url(message.text)
        admin_state[chat_id]['step'] = 'ad_4'
        bot.send_message(chat_id, "🎯 **এবার Task 4 এর লিংক পাঠান:**")
        return
    elif step == 'ad_4' and message.text:
        data = load_data(force_refresh=True)
        ads_map = data.setdefault("ads", {})
        ads_map["ad1"] = admin_state[chat_id]['ad1']
        ads_map["ad2"] = admin_state[chat_id]['ad2']
        ads_map["ad3"] = admin_state[chat_id]['ad3']
        ads_map["ad4"] = extract_single_url(message.text)
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **৪টি টাস্কের (Task 1, 2, 3, 4) লিংক সফলভাবে সেভ হয়েছে!**", reply_markup=get_admin_keyboard())
        return
    elif step == 'set_social_ad' and message.text:
        data = load_data(force_refresh=True)
        data.setdefault("ads", {})["social_ad"] = message.text.strip()
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **সোশ্যাল বার সফলভাবে আপডেট হয়েছে!**", reply_markup=get_admin_keyboard())
        return
    elif step == 'set_native_ad' and message.text:
        data = load_data(force_refresh=True)
        data.setdefault("ads", {})["native_ad"] = message.text.strip()
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **নেটিভ ব্যানার সফলভাবে আপডেট হয়েছে!**", reply_markup=get_admin_keyboard())
        return
    elif step == 'set_popunder_ad' and message.text:
        data = load_data(force_refresh=True)
        data.setdefault("ads", {})["popunder_ad"] = message.text.strip()
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **পপআন্ডার সফলভাবে আপডেট হয়েছে!**", reply_markup=get_admin_keyboard())
        return
    elif step == 'set_video_update' and message.text:
        new_notice = message.text.strip()
        data = load_data(force_refresh=True)
        data["update_notice"] = new_notice
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **ভিডিও আপডেট নোটিশ সেভ হয়েছে!**", reply_markup=get_admin_keyboard())
        return
    elif step == 'add_single_category' and message.text:
        new_c = message.text.strip()
        data = load_data(force_refresh=True)
        cats = data.get("categories", [])
        if new_c and new_c not in cats:
            cats.append(new_c)
            data["categories"] = cats
            save_data(data)
            del admin_state[chat_id]
            bot.send_message(chat_id, f"✅ **'{new_c}' ক্যাটাগরি যুক্ত হয়েছে!**", reply_markup=get_admin_keyboard())
        return
    elif step == 'cs_title' and message.text:
        admin_state[chat_id]['title'] = message.text.strip()
        admin_state[chat_id]['step'] = 'cs_notice'
        bot.send_message(chat_id, "📝 **পপ-আপের নোটিশ লিখে দিন:**")
        return
    elif step == 'cs_notice' and message.text:
        admin_state[chat_id]['notice'] = message.text.strip()
        admin_state[chat_id]['step'] = 'cs_thumb'
        bot.send_message(chat_id, "🖼 **কামিং সুনের থাম্বনেইল ছবি পাঠান:**")
        return
    elif step == 'cs_thumb' and (message.photo or message.text):
        thumb_url = upload_thumb_securely(message.photo[-1].file_id) if message.photo else message.text.strip()
        data = load_data(force_refresh=True)
        new_item = {
            "id": int(time.time()),
            "category": "COMING SOON",
            "is_coming_soon": True,
            "title": admin_state[chat_id]['title'],
            "notice": admin_state[chat_id]['notice'],
            "thumb": thumb_url,
            "date": datetime.now().strftime("%d %B %Y"),
            "time": datetime.now().strftime("%I:%M %p")
        }
        data.setdefault("videos", []).insert(0, new_item)
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **কামিং সুন পোস্ট যুক্ত হয়েছে!**", reply_markup=get_admin_keyboard())
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
        bot.reply_to(message, "🎉 **ভিডিও আপলোড সম্পন্ন হয়েছে! এখনই অ্যাপে দেখা যাবে।**", reply_markup=get_admin_keyboard())
        return
    elif step == 'welcome_video' and message.video:
        data = load_data(force_refresh=True)
        data['welcome_video'] = message.video.file_id
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **ওয়েলকাম ভিডিও সেট হয়েছে!**", reply_markup=get_admin_keyboard())
        return


def internal_self_pinger():
    time.sleep(15)
    while True:
        try:
            requests.get(f"{RENDER_SERVER_URL}/", timeout=10)
        except Exception:
            pass
        time.sleep(540)


def run_polling_loop():
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except Exception:
            time.sleep(2)


if __name__ == "__main__":
    threading.Thread(target=internal_self_pinger, daemon=True).start()
    threading.Thread(target=run_polling_loop, daemon=True).start()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
