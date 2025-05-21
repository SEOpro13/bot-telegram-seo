import logging
import os

from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

from collections import defaultdict

# Configura logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7545362589:AAGIrhr7ESef1Rt9xmt_Zv4Qw9wPqjjRvvE")  # Mejor usar variable de entorno

propuestas = {}
votos = defaultdict(set)
participacion = defaultdict(int)
propuesta_id = 1

# Función faltante para evitar el error
async def saludo_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member and update.my_chat_member.new_chat_member.status == "member":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="¡Gracias por agregarme al grupo! 🎉 Usa /ayuda para ver qué puedo hacer."
        )

# Puedes colocar tus funciones originales aquí: ayuda, proponer, verpropuestas, votar, top, borrar, participacion_cmd, bienvenida_nuevos
# Por ejemplo, una función de ejemplo:
async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Comandos disponibles:\n/proponer\n/verpropuestas\n/votar\n/top\n/borrar\n/participacion"
    )

# Aquí irían las demás funciones (proponer, verpropuestas, votar, etc.)
# ...

### Bot y FastAPI
app = FastAPI()
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Agrega todos tus handlers como antes
bot_app.add_handler(ChatMemberHandler(saludo_grupo, ChatMemberHandler.MY_CHAT_MEMBER))
bot_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bienvenida_nuevos))
bot_app.add_handler(CommandHandler("ayuda", ayuda))
bot_app.add_handler(CommandHandler("proponer", proponer))
bot_app.add_handler(CommandHandler("verpropuestas", verpropuestas))
bot_app.add_handler(CommandHandler("votar", votar))
bot_app.add_handler(CommandHandler("top", top))
bot_app.add_handler(CommandHandler("borrar", borrar))
bot_app.add_handler(CommandHandler("participacion", participacion_cmd))

# Endpoint para recibir Webhooks
@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}
