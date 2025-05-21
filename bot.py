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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "AAGIrhr7ESef1Rt9xmt_Zv4Qw9wPqjjRvvE")  # Mejor usar variable de entorno

propuestas = {}
votos = defaultdict(set)
participacion = defaultdict(int)
propuesta_id = 1

### Lógica de comandos (puedes copiar todas tus funciones originales aquí, como /proponer, /verpropuestas, etc.)
# (aquí van todas tus funciones tal como las tenías, sin cambios)

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
