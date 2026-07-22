import os
import logging
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. HEALTH-CHECK SERVER (Render to'xtab qolmasligi uchun) ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlayapti!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Serverni bot start bo'lishidan oldin alohida thread'da yurgizamiz
threading.Thread(target=run_health_check_server, daemon=True).start()

# --- 2. LOGGING VA TOKENLAR ---
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = "8943737514:AAG2UQQM9PLnU4KPi_tzuaYUczeD14VkoLs"
MOYSKLAD_API_KEY = "462227f5078d111dcd1f300441741229b45563bb"

HEADERS = {
    "Authorization": f"Bearer {MOYSKLAD_API_KEY}",
    "Content-Type": "application/json"
}

# --- 3. MOYSKLAD FUNKSIYALARI ---
def get_moysklad_products():
    """MoySklad'dan mahsulotlar ro'yxatini olish"""
    url = "https://api.moysklad.ru/api/remap/1.2/entity/product"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("rows", [])
    return []

def get_organization_meta():
    """MoySklad'dagi birinchi tashkilot ID (meta)sini avtomatik olish"""
    url = "https://api.moysklad.ru/api/remap/1.2/entity/organization"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        rows = response.json().get("rows", [])
        if rows:
            return rows[0]["meta"]
    return None

def create_customer_order(user_id, first_name, username, product_name, price_val, product_meta):
    """MoySklad'da mijoz va avtomatik 'Заказ покупателя' yaratish"""
    
    # 1-qadam: Kontragentni (Mijozni) qidirish va topilmasa yaratish
    search_name = f"Telegram: {first_name} (@{username if username else user_id})"
    counterparty_url = f"https://api.moysklad.ru/api/remap/1.2/entity/counterparty?search={user_id}"
    res = requests.get(counterparty_url, headers=HEADERS).json()
    
    if res.get("rows") and len(res["rows"]) > 0:
        agent_meta = res["rows"][0]["meta"]
    else:
        # Yangi mijoz (Kontragent) yaratamiz
        new_agent = {
            "name": search_name,
            "code": str(user_id),
            "description": f"Telegram ID: {user_id}"
        }
        agent_res = requests.post(
            "https://api.moysklad.ru/api/remap/1.2/entity/counterparty",
            json=new_agent,
            headers=HEADERS
        ).json()
        agent_meta = agent_res.get("meta")

    org_meta = get_organization_meta()
    if not org_meta or not agent_meta:
        return False, "MoySklad tashkilot yoki mijoz ma'lumotlarida xatolik."

    # 2-qadam: 'Заказ покупателя' yaratish
    order_payload = {
        "organization": {"meta": org_meta},
        "agent": {"meta": agent_meta},
        "description": f"Telegram Bot orqali buyurtma berildi: {product_name}",
        "positions": [
            {
                "quantity": 1,
                "price": price_val,  # MoySklad original kopeykadagi narxi
                "assortment": {"meta": product_meta}
            }
        ]
    }

    order_res = requests.post(
        "https://api.moysklad.ru/api/remap/1.2/entity/customerorder",
        json=order_payload,
        headers=HEADERS
    )

    if order_res.status_code in [200, 201]:
        order_num = order_res.json().get("name", "")
        return True, order_num
    else:
        return False, order_res.text

# --- 4. TELEGRAM BOT HANDLERLARI ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user

    if text == "📦 Mahsulotlar Katalogi":
        await show_catalog(update, context)
    elif text == "📞 Biz bilan bog'lanish":
        await update.message.reply_text("📞 Murojaat uchun: +998 (90) XXX-XX-XX\nOperatorimiz sizga yordam beradi!")
    elif text == "🚚 Yetkazib berish":
        await update.message.reply_text("🚚 Yetkazib berish shartlari:\n- Bepul yetkazib berish!\n- Minimal summa yo'q!")
    else:
        # Matndan nuqta va narxlarni avtomatik tozalaymiz
        clean_text = text.replace("•", "").split("—")[0].strip()

        # MoySklad tovarlari bilan solishtirish
        products = get_moysklad_products()
        matched_product = None
        
        for p in products:
            p_name = p.get("name", "").strip()
            if clean_text.lower() in p_name.lower() or p_name.lower() in clean_text.lower():
                matched_product = p
                break

        if matched_product:
            price_val = matched_product.get("salePrices", [{}])[0].get("value", 0)
            product_meta = matched_product.get("meta")
            prod_name = matched_product.get("name")

            # MoySklad'da avtomatik Заказ yaratamiz
            success, result = create_customer_order(
                user_id=user.id,
                first_name=user.first_name,
                username=user.username,
                product_name=prod_name,
                price_val=price_val,
                product_meta=product_meta
            )

            if success:
                await update.message.reply_text(
                    f"✅ <b>Buyurtma qabul qilindi!</b>\n\n"
                    f"📦 Mahsulot: <b>{prod_name}</b>\n"
                    f"🧾 MoySklad Buyurtma №: <b>{result}</b>\n\n"
                    f"Tez orada operatorimiz siz bilan bog'lanadi.",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    f"Xabaringiz qabul qilindi, lekin MoySklad buyurtmasida xatolik bo'ldi. Operator bog'lanadi."
                )
        else:
            await update.message.reply_text(
                "Xabaringiz qabul qilindi. Tez orada operatorimiz siz bilan bog'lanadi."
            )

# --- 5. MAIN ISHGA TUSHIRISH ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot va HTTP server muvaffaqiyatli ishga tushdi...")
    app.run_polling()
