import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Tokenlar
TELEGRAM_TOKEN = "8943737514:AAG2UQQM9PLnU4KPi_tzuaYUczeD14VkoLs"
MOYSKLAD_API_KEY = "462227f5078d111dcd1f300441741229b45563bb"

logging.basicConfig(level=logging.INFO)

# MoySklad so'rovlar uchun header
HEADERS = {
    "Authorization": f"Bearer {MOYSKLAD_API_KEY}",
    "Content-Type": "application/json"
}

# Start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [KeyboardButton("📦 Mahsulotlar Katalogi")],
        [KeyboardButton("📞 Biz bilan bog'lanish"), KeyboardButton("🚚 Yetkazib berish")]
    ]
    reply_markup = ReplyKeyboardMarkup(kb, resize_keyboard=True)
    await update.message.reply_text(
        "Assalomu alaykum! Bir martalik idishlar botiga xush kelibsiz.\n"
        "Buyurtma berish uchun tugmalardan foydalaning:",
        reply_markup=reply_markup
    )

# MoySklad'dan mahsulotlarni olish
def get_moysklad_products():
    url = "https://api.moysklad.ru/api/remap/1.2/entity/product"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("rows", [])
    return []

# Katalog knopkasi bosilganda
async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = get_moysklad_products()
    if not products:
        await update.message.reply_text("Hozircha mahsulotlar topilmadi yoki MoySklad ulanishida xatolik.")
        return

    msg = "<b>📦 Mahsulotlar ro'yxati:</b>\n\n"
    for p in products[:15]:  # Dastlabki 15 ta mahsulot
        name = p.get("name", "Nomsiz mahsulot")
        # Narxni olish (MoySklad kopeykada beradi, shuning uchun 100 ga bo'lamiz)
        price_rows = p.get("salePrices", [])
        price = price_rows[0].get("value", 0) / 100 if price_rows else 0
        
        msg += f"• <b>{name}</b> — {price:,.0f} so'm\n"

    msg += "\n<i>Buyurtma berish uchun aloqaga chiqing yoki kerakli mahsulot nomini yozib yuboring.</i>"
    await update.message.reply_text(msg, parse_mode="HTML")

# Matnli xabarlar bilan ishlash
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📦 Mahsulotlar Katalogi":
        await show_catalog(update, context)
    elif text == "📞 Biz bilan bog'lanish":
        await update.message.reply_text("📞 Murojaat uchun: +998 (90) XXX-XX-XX\nOperatorimiz sizga yordam beradi!")
    elif text == "🚚 Yetkazib berish":
        await update.message.reply_text("🚚 Yetkazib berish shartlari:\n- Bepul yetkazib berish!\n- Minimal summa yo'q!")
    else:
        await update.message.reply_text("Xabaringiz qabul qilindi. Tez orada operatorimiz siz bilan bog'lanadi.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot ishga tushdi...")
    app.run_polling()

import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlayapti!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Serverni alohida oqimda (thread) yurgizish:
threading.Thread(target=run_health_check_server, daemon=True).start()
