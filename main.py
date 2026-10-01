import telebot
from telebot import types
from flask import Flask, jsonify, make_response
from flask_cors import CORS
import threading
import json
import os
import time
import requests
from datetime import datetime

BOT_TOKEN = "8995171178:AAFwu00-0NGegyHk4USIl_nBufknZZ_4wb4"
ADMIN_ID = "7255626228"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

# --- ক্লাউড ডাটাবেজ কনফিগারেশন (JSONBin.io) ---
BIN_ID = "6abbadacac6210605a01bb77"
JSONBIN_API_KEY = "$2a$10$YXJkOPYEpFL1pS32JSWh7O5Zs7VMzulVbyfBwxBkvPOQ9EY1m0/ri"

BIN_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
HEADERS = {
    "X-Master-Key": JSONBIN_API_KEY,
    "Content-Type": "application/json"
}

# ব্রডকাস্ট মেসেজ ট্র্যাকিং লিস্ট (সবার ইনবক্স থেকে ডিলিট করার জন্য)
broadcast_history = []

def load_data():
    try:
        r = requests.get(f"{BIN_URL}/latest", headers=HEADERS)
        if r.status_code == 200:
            return r.json().get("record", {})
    except Exception as e:
        print("JSONBin Read Error:", e)

    return {
        "users": [],
        "categories": ["BPS5", "Web Series", "Movie"],
        "ads": {"ad1": "https://google.com", "ad2": "https://google.com"},
        "videos": []
    }

def save_data(data):
    try:
        requests.put(BIN_URL, headers=HEADERS, json=data)
    except Exception as e:
        print("JSONBin Save Error:", e)

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

# বাটন জেনারেটর (ব্রডকাস্ট ও স্টার্টের জন্য)
def get_action_buttons():
    fresh_url = f"https://enamulhossen188-ux.github.io/index.html?ts={int(datetime.now().timestamp())}"
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_watch = types.InlineKeyboardButton("🎬 WATCH NOW", web_app=types.WebAppInfo(url=fresh_url))
    btn_update = types.InlineKeyboardButton("🔔 VIDEO UPDATE", callback_data="btn_update")
    btn_help = types.InlineKeyboardButton("💡 যেভাবে ভিডিও ডাউনলোড করবেন", callback_data="btn_help")
    markup.add(btn_watch, btn_update, btn_help)
    return markup

@bot.message_handler(commands=['cancel'])
def cancel_process(message):
    chat_id = message.chat.id
    if chat_id in admin_state:
        del admin_state[chat_id]
        bot.send_message(chat_id, "🔄 আগের অসমাপ্ত কাজ বাতিল করা হয়েছে।", reply_markup=types.ReplyKeyboardRemove())
    else:
        bot.send_message(chat_id, "বর্তমানে কোনো কাজ চালু নেই।")

# --- ক্যাটাগরি প্যানেল ---
@bot.message_handler(commands=['setcategory'])
def manage_categories_menu(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.send_message(message.chat.id, f"অননুমোদিত অ্যাক্সেস! আপনার আইডি: {message.chat.id}")
        return
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

        msg_text = "📁 ক্যাটাগরি কন্ট্রোল প্যানেল:\nEdit করতে [Edit] বাটনে চাপুন।\nDelete করতে [Delete] বাটনে চাপুন।"
        bot.send_message(message.chat.id, msg_text, reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, "Error: " + str(e))

# --- ব্রডকাস্ট কমান্ড ---
@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.send_message(message.chat.id, f"অননুমোদিত অ্যাক্সেস! আপনার আইডি: {message.chat.id}")
        return
    admin_state[message.chat.id] = {'step': 'broadcast_content'}
    bot.send_message(message.chat.id, "📢 সকল ইউজারের কাছে পাঠানোর জন্য নোটিশ বা পোস্টটি (ছবি/ভিডিও/লেখা) পাঠান (বাতিল করতে /cancel দিন):")

# --- ব্রডকাস্ট পোস্ট ডিলিট মেনু (/delpost) ---
@bot.message_handler(commands=['delpost'])
def delete_broadcast_menu(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ আপনি অ্যাডমিন নন!")
        return
    if not broadcast_history:
        bot.send_message(message.chat.id, "ℹ️ ডিলিট করার মতো কোনো ব্রডকাস্ট পোস্ট পাওয়া যায়নি!")
        return
    markup = types.InlineKeyboardMarkup()
    for item in broadcast_history:
        markup.add(types.InlineKeyboardButton(f"🗑️ {item['title']}", callback_data=f"delbc_{item['id']}"))
    bot.send_message(message.chat.id, "🗑 **কোন পোস্টটি সবার ইনবক্স থেকে ডিলিট করতে চান? ক্লিক করুন:**", reply_markup=markup, parse_mode="Markdown")

# --- মোট ইউজার সংখ্যা ও পরিসংখ্যান দেখার কমান্ড (/users ও /stats) ---
@bot.message_handler(commands=['users', 'stats'])
def show_total_users(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ আপনি অ্যাডমিন নন!")
        return

    data = load_data()
    user_list = data.get("users", [])
    total_users = len(user_list)

    msg_text = (
        "📊 **বটের ইউজার পরিসংখ্যান**\n\n"
        f"👥 মোট জয়েনকৃত ইউজার: **{total_users}** জন\n"
        f"🎬 মোট আপলোডকৃত ভিডিও: **{len(data.get('videos', []))}** টি\n"
        f"📁 মোট ক্যাটাগরি: **{len(data.get('categories', []))}** টি"
    )
    bot.send_message(message.chat.id, msg_text, parse_mode="Markdown")

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
        bot.send_message(message.chat.id, "ℹ️️ ডাটাবেজে কোনো ভিডিও নেই!")
        return
    markup = types.InlineKeyboardMarkup()
    for v in videos:
        markup.add(types.InlineKeyboardButton(f"🗑 {v.get('title', 'Unknown')}", callback_data=f"del_{v.get('id')}"))
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

# /start এবং সরাসরি ইনবক্সে ভিডিও ডেলিভারি (ভিডিও স্ট্রিমিং নিশ্চিতকরণ)
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
            caption = f"🎬 **{target_video['title']}**\n\nউপভোগ করুন!"
            try:
                bot.send_video(
                    message.chat.id, 
                    target_video['file_id'], 
                    caption=caption, 
                    parse_mode="Markdown", 
                    protect_content=True,
                    supports_streaming=True
                )
            except Exception as e:
                print("Video send retry/fallback:", e)
                try:
                    bot.send_video(
                        message.chat.id, 
                        target_video['file_id'], 
                        caption=caption, 
                        parse_mode="Markdown", 
                        protect_content=True
                    )
                except Exception:
                    try:
                        bot.send_document(
                            message.chat.id, 
                            target_video['file_id'], 
                            caption=caption, 
                            parse_mode="Markdown", 
                            protect_content=True
                        )
                    except Exception:
                        bot.send_message(message.chat.id, "❌ ভিডিওটি পাঠাতে সমস্যা হচ্ছে।")
            return
        else:
            bot.send_message(message.chat.id, "❌ দুঃখিত, ভিডিওটি পাওয়া যায়নি!")
            return

    markup = get_action_buttons()
    welcome_text = (
        f"**আসসালামু আলাইকুম {message.from_user.first_name}** 🥰\n\n"
        "আমাদের বট ২৪ ঘণ্টা সচল। নাটক দেখতে ও ডাউনলোড করতে নিচের **WATCH NOW** বাটনে ক্লিক করুন।"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")

# --- সেন্ট্রালাইজড কলব্যাক হ্যান্ডলার ---
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    # ১. ক্যাটাগরি যোগ
    if call.data == "add_new_cat":
        msg = bot.send_message(chat_id, "নতুন ক্যাটাগরির নাম লিখে পাঠান (বাতিল করতে /cancel লিখুন):")
        bot.register_next_step_handler(msg, process_add_category)
        return

    # ২. ক্যাটাগরি মোছা
    if call.data.startswith("delcat_"):
        target_cat = call.data.replace("delcat_", "")
        data = load_data()
        cats = data.get("categories", [])
        if target_cat in cats:
            cats.remove(target_cat)
            data["categories"] = cats
            save_data(data)
            bot.send_message(chat_id, f"✅ ক্যাটাগরি '{target_cat}' মুছে ফেলা হয়েছে!")
        else:
            bot.send_message(chat_id, "❌ ক্যাটাগরি পাওয়া যায়নি!")
        return

    # ৩. ক্যাটাগরি নাম পরিবর্তন
    if call.data.startswith("editcat_"):
        old_cat = call.data.replace("editcat_", "")
        msg = bot.send_message(chat_id, f"'{old_cat}' এর নতুন নাম কী দিতে চান? নাম লিখে পাঠান (বাতিল করতে /cancel দিন):")
        bot.register_next_step_handler(msg, lambda m: process_rename_category(m, old_cat))
        return

    # ৪. ব্রডকাস্ট পোস্ট সবার ইনবক্স থেকে ডিলিট করা
    if call.data.startswith("delbc_"):
        if str(chat_id) != str(ADMIN_ID):
            bot.send_message(chat_id, "❌ অনুমতি নেই!")
            return
        target_id = call.data.replace("delbc_", "")
        target_item = next((item for item in broadcast_history if str(item["id"]) == str(target_id)), None)

        if target_item:
            bot.edit_message_text(f"⏳ '{target_item['title']}' পোস্টটি সকলের ইনবক্স থেকে মোছা হচ্ছে...", chat_id=chat_id, message_id=call.message.message_id)
            deleted_count = 0
            for record in target_item["records"]:
                try:
                    bot.delete_message(chat_id=record["chat_id"], message_id=record["msg_id"])
                    deleted_count += 1
                except Exception:
                    pass
            broadcast_history.remove(target_item)
            bot.send_message(chat_id, f"✅ সফলভাবে মোট {deleted_count} জনের ইনবক্স থেকে পোস্ট ও বাটন মুছে ফেলা হয়েছে!")
        else:
            bot.send_message(chat_id, "❌ পোস্টটি পাওয়া যায়নি বা আগেই ডিলিট করা হয়েছে!")
        return

    # ৫. ভিডিও মোছা
    if call.data.startswith("del_"):
        if str(chat_id) != str(ADMIN_ID):
            bot.send_message(chat_id, "❌ অনুমতি নেই!")
            return
        target_id = call.data.replace("del_", "")
        data = load_data()
        videos = data.get("videos", [])
        new_videos = [v for v in videos if str(v.get("id")) != str(target_id)]
        if len(new_videos) < len(videos):
            data["videos"] = new_videos
            save_data(data)
            bot.edit_message_text("🗑️ **ভিডিওটি সফলভাবে ডিলিট করা হয়েছে!**", chat_id=chat_id, message_id=call.message.message_id)
        else:
            bot.send_message(chat_id, "❌ পাওয়া যায়নি!")
        return

    # ৬. তথ্য ও সাহায্য বাটন
    if call.data == "btn_update":
        bot.send_message(chat_id, "📢 **ভিডিও আপডেট:**\nনতুন পর্ব আপলোড করা হয়েছে! স্টার্ট দিয়ে Watch Now থেকে দেখে নিন।", parse_mode="Markdown")
        return

    if call.data == "btn_help":
        bot.send_message(chat_id, "💡 **টিউটোরিয়াল:**\nWatch Now বাটনে ক্লিক করে পছন্দের ভিডিওতে চাপুন। দুটি টাস্ক সম্পন্ন করে ডাউনলোড বাটনে চাপ দিলেই ইনবক্সে ভিডিও চলে আসবে।")
        return

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
    bot.send_message(message.chat.id, f"✅ নতুন ক্যাটাগরি '{new_cat}' সফলভাবে যোগ হয়েছে!")

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
        bot.send_message(message.chat.id, f"✅ ক্যাটাগরি '{old_cat}' পরিবর্তন করে '{new_cat}' করা হয়েছে!")

# --- অ্যাডমিনের ইনপুট হ্যান্ডলার ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_admin_inputs(message):
    chat_id = message.chat.id 
    if str(chat_id) != str(ADMIN_ID) or chat_id not in admin_state:
        return

    step = admin_state[chat_id].get('step')

    # ব্রডকাস্ট পাঠানোর লজিক
    if step == 'broadcast_content':
        if message.text == '/cancel':
            del admin_state[chat_id]
            bot.send_message(chat_id, "বাতিল করা হয়েছে।")
            return

        data = load_data()
        user_list = data.get("users", [])
        bot.send_message(chat_id, f"🚀 {len(user_list)} জনের ইনবক্সে বাটনসহ পোস্ট পাঠানো হচ্ছে...")
        
        sent_records = []
        markup = get_action_buttons()

        raw_text = message.caption if (message.photo or message.video or message.document) else message.text
        if not raw_text:
            raw_text = "Broadcast Message"
        title_snippet = (raw_text[:25] + "...") if len(raw_text) > 25 else raw_text

        for uid in user_list:
            try:
                sent_msg = None
                if message.photo:
                    sent_msg = bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "", reply_markup=markup)
                elif message.video:
                    sent_msg = bot.send_video(uid, message.video.file_id, caption=message.caption or "", reply_markup=markup)
                elif message.document:
                    sent_msg = bot.send_document(uid, message.document.file_id, caption=message.caption or "", reply_markup=markup)
                elif message.text:
                    sent_msg = bot.send_message(uid, message.text, reply_markup=markup)
                
                if sent_msg:
                    sent_records.append({"chat_id": uid, "msg_id": sent_msg.message_id})
                time.sleep(0.04)
            except Exception:
                pass

        if sent_records:
            broadcast_history.append({
                "id": str(len(broadcast_history) + 1),
                "title": title_snippet,
                "records": sent_records
            })

        del admin_state[chat_id]
        bot.send_message(chat_id, f"✅ সফলভাবে {len(sent_records)} জনের ইনবক্সে WATCH NOW বাটনসহ পোস্ট চলে গেছে!\n\n(ভুলবশত এটি ডিলিট করতে চাইলে /delpost কমান্ড দিন)")

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
        bot.send_message(chat_id, "🖼 **থাম্বনেইল ছবি পাঠান:**")

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

# সার্ভার রানার
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    bot.infinity_polling(skip_pending=True)
