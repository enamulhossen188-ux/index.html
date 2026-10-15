import subprocess
import sys

# প্রয়োজনীয় লাইব্রেরি অটো-ইন্সটল
for pkg in ["pyTelegramBotAPI", "Flask", "Flask-CORS", "requests"]:
    try:
        __import__(pkg.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import telebot
from telebot import types
from flask import Flask, jsonify, make_response, send_file, Response
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
DB_CHANNEL_ID = -1004330425245  # নিজস্ব প্রাইভেট চ্যানেল
RENDER_SERVER_URL = "https://my-bot-server-bnj8.onrender.com"
# ====================================================

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)
CORS(app)

cached_data = None
last_cache_time = 0
CACHE_DURATION = 300

admin_state = {}
thumb_memory_cache = {}

def get_default_data():
    return {
        "users": [],
        "categories": ["BPS5", "MOVIES", "DRAMA", "SERIES", "COMING SOON"],
        "sub_categories": {},
        "ads": {
            "ad1": "https://google.com",
            "ad2": "https://google.com",
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
        print("Telegram Pinned DB Read Error:", e)
    return None

def load_data(force_refresh=False):
    global cached_data, last_cache_time
    current_time = time.time()

    if not force_refresh and cached_data and (current_time - last_cache_time < CACHE_DURATION):
        return cached_data

    data = get_db_file_content()
    if data and "videos" in data:
        if "ads" not in data:
            data["ads"] = {}
        if "sub_categories" not in data:
            data["sub_categories"] = {}
        cached_data = data
        last_cache_time = current_time
        return cached_data

    if cached_data:
        return cached_data

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
            caption=f"📦 Database Update (Bot 2): {datetime.now().strftime('%d %b %Y, %I:%M:%S %p')}"
        )
        try:
            bot.pin_chat_message(DB_CHANNEL_ID, sent_doc.message_id, disable_notification=True)
        except Exception:
            pass
    except Exception as e:
        print("Telegram DB Save Error:", e)

def upload_thumb_securely(photo_id):
    try:
        msg = bot.send_photo(DB_CHANNEL_ID, photo_id, caption="🖼 Permanent Thumb")
        perm_file_id = msg.photo[-1].file_id
        return f"{RENDER_SERVER_URL}/thumb/{perm_file_id}"
    except Exception as e:
        print("Channel thumb error:", e)
        return f"{RENDER_SERVER_URL}/thumb/{photo_id}"

@app.route('/thumb/<file_id>')
def serve_thumbnail(file_id):
    global thumb_memory_cache
    if file_id in thumb_memory_cache:
        resp = Response(thumb_memory_cache[file_id], mimetype="image/jpeg")
        resp.headers['Cache-Control'] = 'public, max-age=31536000'
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp

    try:
        file_info = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)
        thumb_memory_cache[file_id] = file_bytes

        resp = Response(file_bytes, mimetype="image/jpeg")
        resp.headers['Cache-Control'] = 'public, max-age=31536000'
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        print("Image proxy failed:", e)
        return Response(status=404)

@app.route('/api/data', methods=['GET'])
def get_app_data():
    data = load_data(force_refresh=True)
    resp = make_response(jsonify(data))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

@app.route('/')
def home():
    if os.path.exists('index.html'):
        return send_file('index.html')
    return "Bot Server Live 24/7!"

def get_action_buttons():
    fresh_url = f"{APP_URL}?ts={int(datetime.now().timestamp())}"
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_watch = types.InlineKeyboardButton("🎬 WATCH NOW", web_app=types.WebAppInfo(url=fresh_url))
    btn_update = types.InlineKeyboardButton("🔔 VIDEO UPDATE", callback_data="btn_update")
    btn_help = types.InlineKeyboardButton("💡 যেভাবে ভিডিও ডাউনলোড করবেন", callback_data="btn_help")
    markup.add(btn_watch, btn_update, btn_help)
    return markup

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("➕ Add Video"),
        types.KeyboardButton("📢 Add Coming Soon"),
        types.KeyboardButton("🔕 Delete Video"),
        types.KeyboardButton("📊 Total Users"),
        types.KeyboardButton("📁 Set Category"),
        types.KeyboardButton("🎯 Set Ads Link"),
        types.KeyboardButton("🎥 Set Welcome Video"),
        types.KeyboardButton("🔔 Set Video Update"),
        types.KeyboardButton("📢 BOT NOTICE")
    )
    return markup

# 🔥 ৪টি আলাদা বিজ্ঞাপনের বাটন 🔥
def get_ads_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔗 1. Task 1 & Task 2 Link", callback_data="set_ad_tasks"),
        types.InlineKeyboardButton("🚀 2. Social Bar Ad Code", callback_data="set_ad_social"),
        types.InlineKeyboardButton("📱 3. Native Banner Ad Code", callback_data="set_ad_native"),
        types.InlineKeyboardButton("💥 4. Popunder Ad Code", callback_data="set_ad_popunder"),
        types.InlineKeyboardButton("❌ বন্ধ করুন (Close)", callback_data="close_admin_menu")
    )
    return markup

def format_button_label(video):
    title = video.get('title', 'Video').strip()
    is_cs = video.get("is_coming_soon") or video.get("category") == "COMING SOON"
    if is_cs: return f"🗑 [📢 CS] {title[:25]}"
    if len(title) > 30: return f"🗑️ {title[:28]}.."
    return f"🗑️ {title}"

def get_delete_view_data(page=0):
    data = load_data(force_refresh=True)
    videos = data.get("videos", [])
    if not videos: return None, None

    per_page = 8
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_videos = videos[start_idx:end_idx]

    text_msg = f"🗑️ **ডিলিট মেনু (পেজ: {page+1}/{(len(videos)+per_page-1)//per_page}):**\n\n"
    markup = types.InlineKeyboardMarkup()

    for idx, v in enumerate(current_videos, start=start_idx + 1):
        is_cs = v.get("is_coming_soon") or v.get("category") == "COMING SOON"
        tag = " [📢 COMING SOON]" if is_cs else ""
        text_msg += f"**{idx}.** {v.get('title')}{tag}\n"
        btn_label = f"{idx}. {format_button_label(v)}"
        markup.add(types.InlineKeyboardButton(btn_label, callback_data=f"delvid_{v.get('id')}_{page}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"delpage_{page-1}"))
    if end_idx < len(videos):
        nav_buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"delpage_{page+1}"))
    
    if nav_buttons: markup.row(*nav_buttons)
    markup.add(types.InlineKeyboardButton("❌ বন্ধ করুন (Close)", callback_data="close_admin_menu"))
    return text_msg, markup

def get_category_keyboard():
    data = load_data(force_refresh=True)
    cats = data.get("categories", ["BPS5", "MOVIES", "DRAMA", "SERIES", "COMING SOON"])
    markup = types.InlineKeyboardMarkup()
    for c in cats:
        markup.add(types.InlineKeyboardButton(f"🗑 Delete: {c}", callback_data=f"delcat_{c}"))
    markup.add(types.InlineKeyboardButton("➕ Add New Category", callback_data="add_new_category"))
    markup.add(types.InlineKeyboardButton("❌ বন্ধ করুন (Close)", callback_data="close_admin_menu"))
    return markup

@bot.message_handler(commands=['admin'])
def open_admin_panel(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ আপনি অ্যাডমিন নন!")
        return
    bot.send_message(message.chat.id, "🛠 **এডমিন প্যানেল সচল করা হয়েছে:**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")

@bot.message_handler(commands=['cancel'])
def cancel_process(message):
    chat_id = message.chat.id
    if chat_id in admin_state:
        del admin_state[chat_id]
        bot.send_message(chat_id, "🔄 আগের অসমাপ্ত কাজ বাতিল করা হয়েছে।", reply_markup=get_admin_keyboard() if str(chat_id) == str(ADMIN_ID) else types.ReplyKeyboardRemove())
    else:
        bot.send_message(chat_id, "বর্তমানে কোনো কাজ চালু নেই।", reply_markup=get_admin_keyboard() if str(chat_id) == str(ADMIN_ID) else types.ReplyKeyboardRemove())

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        data = load_data()
        user_id = message.chat.id
        if "users" not in data: data["users"] = []
        if user_id not in data["users"]:
            data["users"].append(user_id)
            save_data(data)

        text_parts = message.text.split()
        if len(text_parts) > 1 and text_parts[1].startswith("vid_"):
            video_id = text_parts[1].replace("vid_", "")
            target_video = next((v for v in data.get("videos", []) if str(v.get("id")) == str(video_id)), None)
            if target_video and target_video.get("file_id"):
                try:
                    bot.send_video(message.chat.id, target_video['file_id'], caption=f"🎬 **{target_video['title']}**\n\nউপভোগ করুন!", protect_content=True, supports_streaming=True)
                except Exception:
                    bot.send_document(message.chat.id, target_video['file_id'], caption=f"🎬 **{target_video['title']}**")
                return

        markup = get_action_buttons()
        first_name = message.from_user.first_name or "বন্ধু"
        welcome_caption = f"**আসসালামুআলাইকুম {first_name} 🥰**\n\nআমাদের বট ২৪ ঘণ্টা সচল। নাটক দেখতে ও ডাউনলোড করতে নিচের **WATCH NOW** বাটনে ক্লিক করুন।"
        
        welcome_vid = data.get("welcome_video")
        if welcome_vid:
            try:
                bot.send_video(message.chat.id, welcome_vid, caption=welcome_caption, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                bot.send_message(message.chat.id, welcome_caption, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, welcome_caption, reply_markup=markup, parse_mode="Markdown")

        if str(user_id) == str(ADMIN_ID):
            bot.send_message(message.chat.id, "🛠️ **এডমিন প্যানেল সচল করা হয়েছে:**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    except Exception as e:
        print("Start Error:", e)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    
    if call.data == "btn_update":
        bot.answer_callback_query(call.id)
        data = load_data()
        notice_text = data.get("update_notice", "বর্তমানে কোনো নতুন আপডেট নেই। আমাদের সাথেই থাকুন!")
        bot.send_message(chat_id, f"📢 **ভিডিও আপডেট:**\n\n{notice_text}")
        return
    elif call.data == "btn_help":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "💡 **যেভাবে ভিডিও ডাউনলোড করবেন:**\n১. WATCH NOW বাটনে ক্লিক করে অ্যাপে ঢুকুন।\n২. পছন্দের ভিডিও সিলেক্ট করুন।\n৩. দুটি বিজ্ঞাপন ১০ সেকেন্ড করে ভিজিট করুন।\n৪. ডাউনলোড বাটনে চাপ দিলে ভিডিও ইনবক্সে চলে আসবে!")
        return

    if str(chat_id) != str(ADMIN_ID): return

    if call.data == "close_admin_menu":
        bot.delete_message(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # ৪টি আলাদা বিজ্ঞাপনের বাটন হ্যান্ডলার
    if call.data == "set_ad_tasks":
        admin_state[chat_id] = {'step': 'ad_1'}
        bot.send_message(chat_id, "🔗 **Task 1 এর এড লিংক পাঠান:**\n(বাতিল করতে /cancel লিখুন)")
        bot.answer_callback_query(call.id)
        return

    elif call.data == "set_ad_social":
        admin_state[chat_id] = {'step': 'set_social_ad'}
        bot.send_message(chat_id, "🚀 **সোশ্যাল বার (Social Bar) স্ক্রিপ্ট কোড বা লিংকটি পাঠান:**\n(বাতিল করতে /cancel লিখুন)")
        bot.answer_callback_query(call.id)
        return

    elif call.data == "set_ad_native":
        admin_state[chat_id] = {'step': 'set_native_ad'}
        bot.send_message(chat_id, "📱 **ভিডিওর নিচে দেখানোর নেটিভ ব্যানার (Native Banner) কোড বা লিংকটি পাঠান:**\n(বাতিল করতে /cancel লিখুন)")
        bot.answer_callback_query(call.id)
        return

    elif call.data == "set_ad_popunder":
        admin_state[chat_id] = {'step': 'set_popunder_ad'}
        bot.send_message(chat_id, "💥 **পপআন্ডার (Popunder) স্ক্রিপ্ট কোড বা লিংকটি পাঠান:**\n(বাতিল করতে /cancel লিখুন)")
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("delpage_"):
        page = int(call.data.split("_")[1])
        txt, kb = get_delete_view_data(page)
        if kb: bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("delvid_"):
        parts = call.data.split("_")
        del_id = parts[1]
        page = int(parts[2]) if len(parts) > 2 else 0
        data = load_data(force_refresh=True)
        data["videos"] = [v for v in data.get("videos", []) if str(v.get('id')) != str(del_id)]
        save_data(data)
        bot.answer_callback_query(call.id, "✅ সফলভাবে ডিলিট করা হয়েছে!", show_alert=True)
        txt, kb = get_delete_view_data(page)
        if kb: bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        else: bot.edit_message_text("❌ আর কোনো ভিডিও বা পোস্ট নেই!", chat_id, call.message.message_id)
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
    if str(chat_id) != str(ADMIN_ID): return

    if message.text == "➕ Add Video":
        admin_state[chat_id] = {'step': 'category'}
        data = load_data(force_refresh=True)
        cats = data.get("categories", ["BPS5", "MOVIES", "DRAMA", "SERIES"])
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for i in range(0, len(cats), 2):
            markup.row(*[types.KeyboardButton(c) for c in cats[i:i+2]])
        bot.send_message(chat_id, "📁 **ভিডিওর ক্যাটাগরি বেছে নিন:**", reply_markup=markup)
        return

    elif message.text == "📢 Add Coming Soon":
        admin_state[chat_id] = {'step': 'cs_title', 'category': 'COMING SOON', 'is_coming_soon': True}
        bot.send_message(chat_id, "🎬 **কামিং সুন ভিডিওর টাইটেল লিখুন:**", reply_markup=types.ReplyKeyboardRemove())
        return

    elif message.text == "🔕 Delete Video":
        txt, kb = get_delete_view_data(0)
        if not kb:
            bot.send_message(chat_id, "❌ কোনো ভিডিও বা কামিং সুন পোস্ট পাওয়া যায়নি!", reply_markup=get_admin_keyboard())
            return
        bot.send_message(chat_id, txt, reply_markup=kb, parse_mode="Markdown")
        return

    elif message.text == "📊 Total Users":
        data = load_data()
        bot.send_message(chat_id, f"📊 মোট সক্রিয় ইউজার: **{len(data.get('users', []))}** জন\nমোট ভিডিও: **{len(data.get('videos', []))}** টি")
        return

    elif message.text == "📁 Set Category":
        bot.send_message(chat_id, "📁 **ক্যাটাগরি ম্যানেজমেন্ট:**\nমুছতে নামের পাশের বাটনে ক্লিক করুন অথবা নতুন যোগ করুন:", reply_markup=get_category_keyboard())
        return

    elif message.text == "🎯 Set Ads Link":
        bot.send_message(
            chat_id,
            "🎯 **বিজ্ঞাপন সেটিংস:**\nযে ফরম্যাটের বিজ্ঞাপন পরিবর্তন করতে চান তা নির্বাচন করুন:",
            reply_markup=get_ads_keyboard()
        )
        return

    elif message.text == "🎥 Set Welcome Video":
        admin_state[chat_id] = {'step': 'welcome_video'}
        bot.send_message(chat_id, "🎥 **স্টার্টের সময় যে ভিডিওটি শো করবে সেটি পাঠান:**")
        return

    elif message.text == "🔔 Set Video Update":
        admin_state[chat_id] = {'step': 'set_video_update'}
        data = load_data()
        current_up = data.get("update_notice", "বর্তমানে কোনো নতুন আপডেট নেই। আমাদের সাথেই থাকুন!")
        bot.send_message(chat_id, f"🔔 **নোটিশ লিখে পাঠান:**\n`{current_up}`", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
        return

    elif message.text == "📢 BOT NOTICE":
        admin_state[chat_id] = {'step': 'notice_input'}
        bot.send_message(chat_id, "🖼 **নোটিশের ছবি পাঠান অথবা মেসেজ লিখুন:**", reply_markup=types.ReplyKeyboardRemove())
        return

    if chat_id not in admin_state: return
    step = admin_state[chat_id].get('step')

    # ৪টি এড ইনপুট প্রসেসিং
    if step == 'ad_1' and message.text:
        admin_state[chat_id]['ad1'] = message.text.strip()
        admin_state[chat_id]['step'] = 'ad_2'
        bot.send_message(chat_id, "🎯 **এবার Task 2 এর এড লিংক পাঠান:**")
        return

    elif step == 'ad_2' and message.text:
        data = load_data(force_refresh=True)
        ads_map = data.setdefault("ads", {})
        ads_map["ad1"] = admin_state[chat_id]['ad1']
        ads_map["ad2"] = message.text.strip()
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **টাস্ক ১ এবং ২ এর লিংক সেভ হয়েছে!**", reply_markup=get_admin_keyboard())
        return

    elif step == 'set_social_ad' and message.text:
        data = load_data(force_refresh=True)
        ads_map = data.setdefault("ads", {})
        ads_map["social_ad"] = message.text.strip()
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **সোশ্যাল বার (Social Bar) এড কোড সফলভাবে আপডেট হয়েছে!**", reply_markup=get_admin_keyboard())
        return

    elif step == 'set_native_ad' and message.text:
        data = load_data(force_refresh=True)
        ads_map = data.setdefault("ads", {})
        ads_map["native_ad"] = message.text.strip()
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **নেটিভ ব্যানার (Native Banner) এড কোড সফলভাবে আপডেট হয়েছে!**", reply_markup=get_admin_keyboard())
        return

    elif step == 'set_popunder_ad' and message.text:
        data = load_data(force_refresh=True)
        ads_map = data.setdefault("ads", {})
        ads_map["popunder_ad"] = message.text.strip()
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **পপআন্ডার (Popunder) এড কোড সফলভাবে আপডেট হয়েছে!**", reply_markup=get_admin_keyboard())
        return

    elif step == 'set_video_update' and message.text:
        new_notice = message.text.strip()
        data = load_data(force_refresh=True)
        data["update_notice"] = new_notice
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, f"✅ **ভিডিও আপডেট সফলভাবে সেট করা হয়েছে!**\n\n\"{new_notice}\"", reply_markup=get_admin_keyboard())
        return

    elif step == 'add_single_category' and message.text:
        new_c = message.text.strip().upper()
        data = load_data(force_refresh=True)
        cats = data.get("categories", [])
        if new_c and new_c not in cats:
            cats.append(new_c)
            data["categories"] = cats
            save_data(data)
            del admin_state[chat_id]
            bot.send_message(chat_id, f"✅ **'{new_c}' ক্যাটাগরি সফলভাবে যুক্ত হয়েছে!**", reply_markup=get_admin_keyboard())
        else:
            bot.send_message(chat_id, "⚠️ এই ক্যাটাগরি ইতিমধ্যে রয়েছে অথবা ভুল নাম দিয়েছেন।")
        return

    elif step == 'notice_input' and (message.photo or message.text):
        data = load_data()
        user_list = data.get("users", [])
        bot.send_message(chat_id, f"⏳ **{len(user_list)} জন ইউজারের কাছে নোটিশ পাঠানো শুরু হয়েছে...**", reply_markup=get_admin_keyboard())
        del admin_state[chat_id]

        fresh_url = f"{APP_URL}?ts={int(datetime.now().timestamp())}"
        notice_markup = types.InlineKeyboardMarkup()
        btn_watch = types.InlineKeyboardButton("🎬 WATCH NOW", web_app=types.WebAppInfo(url=fresh_url))
        notice_markup.add(btn_watch)

        is_photo = bool(message.photo)
        photo_id = message.photo[-1].file_id if is_photo else None
        caption_text = message.caption or (message.text if not is_photo else "")

        sent = 0
        for uid in user_list:
            try:
                if is_photo:
                    bot.send_photo(uid, photo_id, caption=caption_text, reply_markup=notice_markup)
                else:
                    bot.send_message(uid, f"📢 **নোটিশ:**\n\n{caption_text}", reply_markup=notice_markup, parse_mode="Markdown")
                sent += 1
                time.sleep(0.04)
            except Exception:
                pass
        bot.send_message(chat_id, f"✅ মোট **{sent}** জন ইউজারের কাছে নোটিশ পাঠানো সম্পন্ন!")
        return

    elif step == 'cs_title' and message.text:
        admin_state[chat_id]['title'] = message.text.strip()
        admin_state[chat_id]['step'] = 'cs_notice'
        bot.send_message(chat_id, "📝 **পপ-আপে কী নোটিশ শো করবে তা লিখে দিন:**")
        return

    elif step == 'cs_notice' and message.text:
        admin_state[chat_id]['notice'] = message.text.strip()
        admin_state[chat_id]['step'] = 'cs_thumb'
        bot.send_message(chat_id, "🖼 **কামিং সুন পোস্টের থাম্বনেইল ছবি পাঠান:**")
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
        bot.send_message(chat_id, "✅ **কামিং সুন পোস্ট সফলভাবে যুক্ত হয়েছে!**", reply_markup=get_admin_keyboard())
        return

    elif step == 'category' and message.text:
        admin_state[chat_id]['category'] = message.text.strip().upper()
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
        file_id = message.video.file_id if message.video else message.document.file_id
        data = load_data(force_refresh=True)
        new_video = {
            "id": int(time.time()),
            "category": admin_state[chat_id]['category'],
            "title": admin_state[chat_id]['title'],
            "thumb": admin_state[chat_id]['thumb'],
            "file_id": file_id,
            "date": datetime.now().strftime("%d %B %Y"),
            "time": datetime.now().strftime("%I:%M %p")
        }
        data.setdefault("videos", []).insert(0, new_video)
        save_data(data)
        del admin_state[chat_id]
        bot.reply_to(message, "🎉 **ভিডিও সফলভাবে আপলোড হয়েছে!**", reply_markup=get_admin_keyboard())
        return

    elif step == 'welcome_video' and message.video:
        data = load_data(force_refresh=True)
        data['welcome_video'] = message.video.file_id
        save_data(data)
        del admin_state[chat_id]
        bot.send_message(chat_id, "✅ **ওয়েলকাম ভিডিও সেট হয়েছে!**", reply_markup=get_admin_keyboard())
        return

def run_bot():
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.daemon = True
    t.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
