# bot.py

import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ChatMemberHandler,
    filters,
)
import database  # tu database.py con httpx

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = 1011479473

# --- Comandos ---

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🤖 *Comandos disponibles:*\n"
        "/proponer <texto>\n"
        "/verpropuestas\n"
        "/votar <id>\n"
        "/top\n"
        "/borrar <id>\n"
        "/participacion\n"
        "/reiniciar (solo admin)"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")

async def proponer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Uso: /proponer <texto>")
    texto = " ".join(context.args)
    pid = await database.registrar_propuesta(texto, update.effective_user)
    await update.message.reply_text(f"✅ Propuesta #{pid} registrada:\n» {texto}")

async def verpropuestas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await database.obtener_propuestas()
    if not rows:
        return await update.message.reply_text("No hay propuestas aún.")
    mensaje = "📋 *Propuestas actuales:*\n"
    for r in rows:
        mensaje += f"#{r['id']}: {r['texto']} (👤 {r['nombre_autor']}, 👍 {r['votos']})\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def votar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Uso: /votar <id>")
    pid = int(context.args[0])
    uid = update.effective_user.id
    res = await database.votar_por_propuesta(pid, uid)
    await update.message.reply_text(res)

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await database.obtener_top_propuestas()
    if not rows:
        return await update.message.reply_text("No hay propuestas aún.")
    mensaje = "🏆 *Top propuestas:*\n"
    for r in rows:
        mensaje += f"#{r['id']}: {r['texto']} (👍 {r['votos']})\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Uso: /borrar <id>")
    pid = int(context.args[0])
    uid = update.effective_user.id
    res = await database.borrar_propuesta(pid, uid)
    await update.message.reply_text(res)

async def participacion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await database.obtener_participacion()
    if not rows:
        return await update.message.reply_text("Nadie ha participado aún.")
    mensaje = "📊 *Participación:*\n"
    for r in rows:
        member = await context.bot.get_chat_member(update.effective_chat.id, r["uid"])
        nombre = member.user.first_name
        mensaje += f"{nombre}: {r['count']} propuestas\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Solo admin puede usar este comando.")
    await database.reiniciar_datos()
    await update.message.reply_text("🔄 Datos reiniciados. ¡Nueva ronda!")

async def saludo_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member.new_chat_member.status == "member":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="¡Gracias por invitarme! Usa /ayuda para empezar."
        )

async def bienvenida_nuevos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for m in update.message.new_chat_members:
        await update.message.reply_text(f"👋 ¡Bienvenido/a {m.first_name}!")

# --- FastAPI & Bot Setup ---

app = FastAPI()
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Commands
handlers = {
    "ayuda": ayuda, "proponer": proponer, "verpropuestas": verpropuestas,
    "votar": votar, "top": top, "borrar": borrar,
    "participacion": participacion_cmd, "reiniciar": reiniciar
}
for cmd, fn in handlers.items():
    bot_app.add_handler(CommandHandler(cmd, fn))

# Group events
bot_app.add_handler(ChatMemberHandler(saludo_grupo, ChatMemberHandler.MY_CHAT_MEMBER))
bot_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bienvenida_nuevos))

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}

@app.get("/")
async def root():
    return JSONResponse({"status": "Bot en funcionamiento 🚀"})

@app.on_event("startup")
async def on_startup():
    await bot_app.initialize()

@app.on_event("shutdown")
async def on_shutdown():
    await bot_app.shutdown()
