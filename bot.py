import logging
import sqlite3
import re
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ================== KONFIGURASI ==================
import os
TOKEN = os.getenv("TOKEN", "8784331466:AAGdFY5mJk17B8VFm2swAX-vhOp1P72xOa0")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5595031501"))
ADMIN_USENAME = "whatsappchinese"
TESTI_LINK = "https://t.me/chinesewsandwc"
DB = "blastbot.db"

logging.basicConfig(level=logging.INFO)

# ================== DATABASE ==================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        phone TEXT,
        lang TEXT DEFAULT 'id',
        balance INTEGER DEFAULT 0,
        mode TEXT,
        banned INTEGER DEFAULT 0,
        joined TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS pending (
        user_id INTEGER PRIMARY KEY,
        phone TEXT,
        mode TEXT,
        stage TEXT
    )""")
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def is_banned(user_id):
    u = get_user(user_id)
    return bool(u and u[6])

def upsert_user(user_id, username=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, lang, joined) VALUES (?,?,?,?)",
                  (user_id, username, 'id', datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_user(user_id, **kwargs):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for k, v in kwargs.items():
        c.execute(f"UPDATE users SET {k}=? WHERE user_id=?", (v, user_id))
    conn.commit()
    conn.close()

def set_pending(user_id, phone=None, mode=None, stage=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO pending (user_id, phone, mode, stage) VALUES (?,?,?,?)",
              (user_id, phone, mode, stage))
    conn.commit()
    conn.close()

def get_pending(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT phone, mode, stage FROM pending WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def clear_pending(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM pending WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# ================== TEKS MULTI BAHASA ==================
TEXTS = {
    "id": {
        "welcome": ("Halo! Selamat Datang Di Penyewaan Whatsapp \n\n"
                    "DB ON \nRATE 1,1K/CHAT\nSUPPORT ALL NEGARA\n\n"
                    "SILAHKAN LANJUTKAN DENGAN MENGKLIK MENU DI BAWAH INI!"),
        "menu_blast": "Mulai Blast", "menu_profile": "Profil", "menu_wd": "Tarik Uang",
        "menu_ref": "Referral", "menu_cs": "Hubungi CS", "menu_hist": "History",
        "menu_lang": "Bahasa", "menu_rank": "Cek Papan Peringkat", "menu_app": "Mini App",
        "ask_number": "Silakan kirim nomor HP yang ingin ditautkan (contoh: 6281234567890):",
        "invalid_number": "❌ Nomor tidak valid. Kirim angka saja, contoh: 6281234567890",
        "submitted": "✅ Nomor Berhasil Di Ajukan Dengan Metode Kode Pairing\n\n⏳ Tunggu kode pairing dari admin...",
        "code_sent": "Kode Pairing Adalah {code}\n\nSilahkan Digunakan",
        "kode_btn_ok": "✅ Kode Berhasil",
        "kode_btn_fail": "❌ Kode Salah",
        "blast_started": "🚀 Nomor Sedang Di Blast",
        "banned_menu": "⚠️ Nomor Telah Banned",
        "wd_min": "❌ Minimal penarikan Rp5.000",
        "wd_ask_amount": "Masukkan nominal penarikan (min Rp5.000):",
        "wd_ask_method": "Masukkan metode & nomor tujuan (contoh: DANA 08123456789):",
        "wd_sent": "✅ Permintaan penarikan dikirim, tunggu konfirmasi admin.",
        "ref": f"🔧 Referral sedang Maintenance\n\nLihat testimoni: {TESTI_LINK}",
        "rank": "🔧 Papan Peringkat sedang Maintenance",
        "hist": "🔧 History sedang Maintenance",
        "app": "❌ Error 404",
        "choose_lang": "Pilih bahasa:",
        "lang_set": "✅ Bahasa diubah ke Indonesia",
    },
    "en": {
        "welcome": ("Hello! Welcome to Whatsapp Rental \n\n"
                    "DB ON \nRATE 1.1K/CHAT\nSUPPORT ALL COUNTRIES\n\n"
                    "PLEASE CONTINUE BY CLICKING THE MENU BELOW!"),
        "menu_blast": "Start Blast", "menu_profile": "Profile", "menu_wd": "Withdraw",
        "menu_ref": "Referral", "menu_cs": "Contact CS", "menu_hist": "History",
        "menu_lang": "Language", "menu_rank": "Leaderboard", "menu_app": "Mini App",
        "ask_number": "Please send the phone number to link (e.g. 6281234567890):",
        "invalid_number": "❌ Invalid number. Send digits only.",
        "submitted": "✅ Number Successfully Submitted With Pairing Code Method\n\n⏳ Waiting for pairing code from admin...",
        "code_sent": "Pairing Code Is {code}\n\nPlease Use It",
        "kode_btn_ok": "✅ Code Success",
        "kode_btn_fail": "❌ Code Wrong",
        "blast_started": "🚀 Number is Being Blasted",
        "banned_menu": "⚠️ Number Has Been Banned",
        "wd_min": "❌ Minimum withdrawal Rp5,000",
        "wd_ask_amount": "Enter withdrawal amount (min Rp5,000):",
        "wd_ask_method": "Enter method & destination (e.g. DANA 08123456789):",
        "wd_sent": "✅ Withdrawal request sent, wait for admin confirmation.",
        "ref": f"🔧 Referral under Maintenance\n\nSee testimonials: {TESTI_LINK}",
        "rank": "🔧 Leaderboard under Maintenance",
        "hist": "🔧 History under Maintenance",
        "app": "❌ Error 404",
        "choose_lang": "Choose language:",
        "lang_set": "✅ Language changed to English",
    },
    "zh": {
        "welcome": ("你好！欢迎来到 WhatsApp 租赁 \n\n"
                    "DB ON \n费率 1.1K/聊天\n支持所有国家\n\n"
                    "请点击下方菜单继续！"),
        "menu_blast": "开始群发", "menu_profile": "个人资料", "menu_wd": "提现",
        "menu_ref": "推荐", "menu_cs": "联系客服", "menu_hist": "历史记录",
        "menu_lang": "语言", "menu_rank": "排行榜", "menu_app": "小程序",
        "ask_number": "请发送要绑定的电话号码 (例: 6281234567890):",
        "invalid_number": "❌ 号码无效。请仅发送数字。",
        "submitted": "✅ 号码已通过配对码方式成功提交\n\n⏳ 等待管理员发送配对码...",
        "code_sent": "配对码是 {code}\n\n请使用",
        "kode_btn_ok": "✅ 配对成功",
        "kode_btn_fail": "❌ 配对错误",
        "blast_started": "🚀 号码正在群发中",
        "banned_menu": "⚠️ 号码已被封禁",
        "wd_min": "❌ 最低提现 Rp5.000",
        "wd_ask_amount": "输入提现金额 (最低 Rp5.000):",
        "wd_ask_method": "输入方式及账号 (例: DANA 08123456789):",
        "wd_sent": "✅ 提现请求已发送，请等待管理员确认。",
        "ref": f"🔧 推荐功能维护中\n\n查看客户评价: {TESTI_LINK}",
        "rank": "🔧 排行榜维护中",
        "hist": "🔧 历史记录维护中",
        "app": "❌ 错误 404",
        "choose_lang": "选择语言:",
        "lang_set": "✅ 语言已切换为中文",
    },
}

def T(user_id, key):
    u = get_user(user_id)
    lang = u[3] if u else "id"
    return TEXTS.get(lang, TEXTS["id"]).get(key, key)

# ================== KEYBOARD ==================
def main_menu(user_id):
    kb = [
        [KeyboardButton(T(user_id, "menu_blast"))],
        [KeyboardButton(T(user_id, "menu_profile")), KeyboardButton(T(user_id, "menu_wd"))],
        [KeyboardButton(T(user_id, "menu_ref")), KeyboardButton(T(user_id, "menu_cs"))],
        [KeyboardButton(T(user_id, "menu_hist")), KeyboardButton(T(user_id, "menu_lang"))],
        [KeyboardButton(T(user_id, "menu_rank"))],
        [KeyboardButton(T(user_id, "menu_app"), web_app=WebAppInfo(url="https://example.com"))],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def mode_menu():
    kb = [
        [KeyboardButton("Brutal (0.1 Detik)")],
        [KeyboardButton("Cepat (1 Detik)")],
        [KeyboardButton("Mayan (5 Detik)")],
        [KeyboardButton("Normal (10 Detik)")],
        [KeyboardButton("Slow (30 Detik)")],
        [KeyboardButton("Cacing (60 Detik)")],
        [KeyboardButton("Keong (90 Detik)")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def lang_menu():
    kb = [
        [KeyboardButton("🇮🇩 Indonesia")],
        [KeyboardButton("🇨🇳 China")],
        [KeyboardButton("🇬🇧 English")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def kode_menu(user_id):
    kb = [
        [KeyboardButton(T(user_id, "kode_btn_ok"))],
        [KeyboardButton(T(user_id, "kode_btn_fail"))],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# ================== HANDLERS USER ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_banned(user.id):
        return  # user dibanned → diam total
    upsert_user(user.id, user.username)
    clear_pending(user.id)
    await update.message.reply_text(T(user.id, "welcome"), reply_markup=main_menu(user.id))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Kalau user dibanned → DIAM TOTAL
    if is_banned(user.id):
        return

    text = update.message.text.strip()
    upsert_user(user.id, user.username)
    pending = get_pending(user.id)
    stage = pending[2] if pending else None

    # ==== Cek bahasa ====
    if text in ["🇮🇩 Indonesia", "🇨🇳 China", "🇬🇧 English"]:
        lang_map = {"🇮🇩 Indonesia": "id", "🇨🇳 China": "zh", "🇬🇧 English": "en"}
        update_user(user.id, lang=lang_map[text])
        await update.message.reply_text(T(user.id, "lang_set"), reply_markup=main_menu(user.id))
        return

    # ==== Tombol Kode Berhasil / Kode Salah ====
    if text in [TEXTS[l]["kode_btn_ok"] for l in TEXTS] or text in [TEXTS[l]["kode_btn_fail"] for l in TEXTS]:
        if stage == "waiting_code_result":
            ok = text in [TEXTS[l]["kode_btn_ok"] for l in TEXTS]
            status = "✅ KODE BERHASIL" if ok else "❌ KODE SALAH"
            await context.bot.send_message(
                ADMIN_ID,
                f"📢 *Update Status Kode*\n\n"
                f"👤 @{user.username or '-'} (ID: `{user.id}`)\n"
                f"📱 Nomor: `{pending[0]}`\n"
                f"Status: *{status}*",
                parse_mode="Markdown"
            )
            if ok:
                set_pending(user.id, phone=pending[0], stage="waiting_mode")
                await update.message.reply_text(
                    "✅ Kode diterima!\n\nPilihlah Mode Blast:",
                    reply_markup=mode_menu()
                )
            else:
                await update.message.reply_text(
                    "❌ Kode salah. Silakan hubungi admin untuk kode baru.",
                    reply_markup=main_menu(user.id)
                )
                clear_pending(user.id)
        return

    # ==== Proses kirim nomor ====
    if stage == "waiting_number":
        nomor = text.replace(" ", "").replace("+", "").replace("-", "")
        if not nomor.isdigit() or len(nomor) < 8:
            await update.message.reply_text(T(user.id, "invalid_number"))
            return
        update_user(user.id, phone=nomor)
        set_pending(user.id, phone=nomor, stage="waiting_code")
        await update.message.reply_text(T(user.id, "submitted"), reply_markup=main_menu(user.id))
        await context.bot.send_message(
            ADMIN_ID,
            f"📥 *Pengajuan Nomor Baru (Pairing Code)*\n\n"
            f"👤 User: @{user.username or '-'}\n"
            f"🆔 ID: `{user.id}`\n"
            f"📱 Nomor: `{nomor}`\n\n"
            f"➡️ *Reply pesan ini dengan KODE 8 DIGIT* untuk diteruskan ke user.\n"
            f"Contoh: `12345678`",
            parse_mode="Markdown"
        )
        return

    # ==== Pilih Mode Blast ====
    modes = ["Brutal (0.1 Detik)", "Cepat (1 Detik)", "Mayan (5 Detik)",
             "Normal (10 Detik)", "Slow (30 Detik)", "Cacing (60 Detik)", "Keong (90 Detik)"]
    if text in modes and stage == "waiting_mode":
        set_pending(user.id, phone=pending[0], mode=text, stage="blasting")
        update_user(user.id, mode=text)
        await update.message.reply_text(T(user.id, "blast_started"), reply_markup=main_menu(user.id))
        await context.bot.send_message(
            ADMIN_ID,
            f"⚡ *User Memilih Mode Blast*\n\n"
            f"👤 @{user.username or '-'} (ID: `{user.id}`)\n"
            f"📱 Nomor: `{pending[0]}`\n"
            f"🎯 Mode: *{text}*\n\n"
            f"➡️ Reply pesan ini untuk kirim pesan ke user.\n"
            f"➡️ Klik tombol di bawah untuk lapor ban.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚠️ Nomor Telah Banned", callback_data=f"banned_{user.id}")
            ]])
        )
        return

    # ==== Menu Mulai Blast ====
    if text in [TEXTS[l]["menu_blast"] for l in TEXTS]:
        set_pending(user.id, stage="waiting_number")
        await update.message.reply_text(
            T(user.id, "ask_number"),
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ Batal")]], resize_keyboard=True)
        )
        return

    if text == "❌ Batal":
        clear_pending(user.id)
        await update.message.reply_text("Dibatalkan.", reply_markup=main_menu(user.id))
        return

    # ==== Profil ====
    if text in [TEXTS[l]["menu_profile"] for l in TEXTS]:
        u = get_user(user.id)
        await update.message.reply_text(
            f"👤 *Profil*\n\n"
            f"🆔 ID: `{user.id}`\n"
            f"📱 Nomor: `{u[2] or '-'}`\n"
            f"💰 Saldo: *Rp{u[4]:,}*\n"
            f"🎯 Mode: {u[5] or '-'}\n"
            f"🌐 Bahasa: {u[3].upper()}\n"
            f"📅 Join: {u[7][:10] if u[7] else '-'}\n\n"
            f"💳 Metode Penarikan: DANA / OVO / GOPAY",
            parse_mode="Markdown"
        )
        return

    # ==== Tarik Uang ====
    if text in [TEXTS[l]["menu_wd"] for l in TEXTS]:
        set_pending(user.id, stage="waiting_wd_amount")
        await update.message.reply_text(
            T(user.id, "wd_ask_amount"),
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ Batal")]], resize_keyboard=True)
        )
        return

    if stage == "waiting_wd_amount":
        try:
            amount = int(text.replace(".", "").replace(",", ""))
        except:
            await update.message.reply_text("❌ Masukkan angka yang valid.")
            return
        if amount < 5000:
            await update.message.reply_text(T(user.id, "wd_min"))
            return
        set_pending(user.id, phone=str(amount), stage="waiting_wd_method")
        await update.message.reply_text(T(user.id, "wd_ask_method"))
        return

    if stage == "waiting_wd_method":
        amount = pending[0]
        await update.message.reply_text(T(user.id, "wd_sent"), reply_markup=main_menu(user.id))
        await context.bot.send_message(
            ADMIN_ID,
            f"💸 *Permintaan Tarik Uang*\n\n"
            f"👤 @{user.username or '-'} (ID: `{user.id}`)\n"
            f"💰 Jumlah: *Rp{int(amount):,}*\n"
            f"🏦 Metode: {text}",
            parse_mode="Markdown"
        )
        clear_pending(user.id)
        return

    # ==== Menu lain ====
    if text in [TEXTS[l]["menu_ref"] for l in TEXTS]:
        await update.message.reply_text(T(user.id, "ref")); return
    if text in [TEXTS[l]["menu_cs"] for l in TEXTS]:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Chat Admin", url=f"https://t.me/{ADMIN_USERNAME}")]])
        await update.message.reply_text("Klik tombol di bawah untuk chat admin:", reply_markup=kb)
        return
    if text in [TEXTS[l]["menu_hist"] for l in TEXTS]:
        await update.message.reply_text(T(user.id, "hist")); return
    if text in [TEXTS[l]["menu_lang"] for l in TEXTS]:
        await update.message.reply_text(T(user.id, "choose_lang"), reply_markup=lang_menu()); return
    if text in [TEXTS[l]["menu_rank"] for l in TEXTS]:
        await update.message.reply_text(T(user.id, "rank")); return
    if text in [TEXTS[l]["menu_app"] for l in TEXTS]:
        await update.message.reply_text(T(user.id, "app")); return

    await update.message.reply_text("Ketik /start untuk kembali ke menu utama.")

# ================== CALLBACK TOMBOL ADMIN ==================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # Cek apakah pengklik adalah admin
    if q.from_user.id != ADMIN_ID:
        await q.message.reply_text("Tolol, Ini Command Khusus Admin")
        return

    data = q.data
    # Tombol ⚠️ Nomor Telah Banned
    if data.startswith("banned_"):
        uid = int(data.split("_")[1])
        set_pending(ADMIN_ID, phone=str(uid), stage="waiting_ban_count")
        await q.message.reply_text(
            f"📊 *Lapor Ban User*\n\n"
            f"👤 User ID: `{uid}`\n\n"
            f"Ketik total blast yang berhasil terkirim (angka saja).\n"
            f"Contoh: `1247`",
            parse_mode="Markdown"
        )
        return

    # Tombol ✅ Sukses / ❌ Tidak Sukses (dari notif pengajuan nomor)
    if data.startswith("approve_") or data.startswith("reject_"):
        action, uid = data.split("_")
        uid = int(uid)
        if action == "approve":
            set_pending(uid, stage="waiting_code_result")
            await context.bot.send_message(
                uid,
                "✅ Pengajuan kamu disetujui admin.\n\nSilakan tunggu kode pairing...",
                reply_markup=main_menu(uid)
            )
            await q.message.reply_text(f"✅ Notif terkirim ke user `{uid}`.", parse_mode="Markdown")
        else:
            await context.bot.send_message(uid, "❌ Pengajuan nomor ditolak admin.")
            clear_pending(uid)
            await q.message.reply_text(f"❌ User `{uid}` ditolak.", parse_mode="Markdown")
        return

# ================== HANDLER ADMIN ==================
async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Semua pesan admin masuk sini (admin-only)."""
    text = (update.message.text or "").strip()

    # ---------- /saldo <id> <jumlah> ----------
    if text.startswith("/saldo"):
        parts = text.split()
        if len(parts) == 3:
            try:
                uid = int(parts[1]); amt = int(parts[2])
            except:
                await update.message.reply_text("Format: /saldo <user_id> <jumlah>")
                return
            u = get_user(uid)
            if u:
                update_user(uid, balance=u[4] + amt)
                await context.bot.send_message(uid, f"💰 Saldo kamu bertambah *Rp{amt:,}*", parse_mode="Markdown")
                await update.message.reply_text(f"✅ Berhasil. Saldo user {uid} +Rp{amt:,}")
            else:
                await update.message.reply_text("❌ User tidak ditemukan.")
        else:
            await update.message.reply_text("Format: /saldo <user_id> <jumlah>")
        return

    # ---------- /banuser <id> ----------
    if text.startswith("/banuser"):
        parts = text.split()
        if len(parts) == 2:
            try:
                uid = int(parts[1])
            except:
                await update.message.reply_text("Format: /banuser <user_id>")
                return
            u = get_user(uid)
            if not u:
                await update.message.reply_text("❌ User tidak ditemukan.")
                return
            update_user(uid, banned=1)
            await update.message.reply_text(f"✅ Berhasil. User {uid} telah dibanned.")
        else:
            await update.message.reply_text("Format: /banuser <user_id>")
        return

    # ---------- /unban <id> ----------
    if text.startswith("/unban"):
        parts = text.split()
        if len(parts) == 2:
            try:
                uid = int(parts[1])
            except:
                await update.message.reply_text("Format: /unban <user_id>")
                return
            u = get_user(uid)
            if not u:
                await update.message.reply_text("❌ User tidak ditemukan.")
                return
            update_user(uid, banned=0)
            await update.message.reply_text(f"✅ User {uid} telah di-unban.")
        else:
            await update.message.reply_text("Format: /unban <user_id>")
        return

    # ---------- Admin sedang isi total blast buat lapor ban ----------
    p = get_pending(ADMIN_ID)
    if p and p[2] == "waiting_ban_count":
        try:
            count = int(text.replace(".", "").replace(",", ""))
        except:
            await update.message.reply_text("❌ Ketik angka saja. Contoh: 1247")
            return
        uid = int(p[0])
        await context.bot.send_message(
            uid,
            f"⚠️ Nomor Kamu Telah Banned\n\n"
            f"✅ Total blast berhasil: {count:,} pesan terkirim",
            reply_markup=main_menu(uid)
        )
        clear_pending(ADMIN_ID)
        await update.message.reply_text(f"✅ Laporan ban terkirim ke user {uid} ({count:,} blast).")
        return

    # ---------- Reply pesan notif ----------
    if update.message.reply_to_message:
        replied = update.message.reply_to_message.text or ""
        m = re.search(r"ID: `?(\d+)`?", replied)
        mn = re.search(r"Nomor: `?(\d+)`?", replied)

        # Kalau reply notif pengajuan nomor & isinya 8 digit
        if m and mn and ("Pengajuan Nomor" in replied or "Pairing" in replied):
            uid = int(m.group(1))
            phone = mn.group(1)
            kode = text.strip()
            if not re.fullmatch(r"\d{8}", kode):
                await update.message.reply_text("❌ Kode harus 8 digit angka. Contoh: 12345678")
                return
            set_pending(uid, phone=phone, stage="waiting_code_result")
            await context.bot.send_message(
                uid,
                T(uid, "code_sent").format(code=kode),
                reply_markup=kode_menu(uid)
            )
            await update.message.reply_text(f"✅ Kode `{kode}` terkirim ke user `{uid}`.", parse_mode="Markdown")
            return

        # Kalau reply notif mode blast → teruskan ke user
        if m and ("Mode Blast" in replied or "Pengajuan" in replied):
            uid = int(m.group(1))
            try:
                await context.bot.send_message(uid, text)
                await update.message.reply_text("✅ Pesan terkirim ke user.")
            except Exception as e:
                await update.message.reply_text(f"❌ Gagal kirim: {e}")
            return

# ================== USER COBA COMMAND ADMIN ==================
async def user_try_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kalau user biasa ketik command admin → balas pesan tolak."""
    await update.message.reply_text("Tolol, Ini Command Khusus Admin")

# ================== RUN ==================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    # Handler command user (start)
    app.add_handler(CommandHandler("start", start))

    # Callback tombol
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Handler admin-only (group 0)
    app.add_handler(MessageHandler(filters.User(ADMIN_ID), admin_handler), group=0)

    # Handler user biasa yang ketik command admin → tolak
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^/(saldo|banuser|unban)"),
        user_try_admin
    ), group=1)

    # Handler pesan user biasa
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text), group=2)

    print("🚀 Bot jalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
