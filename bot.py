# bot.py

import logging
import os
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, ChatMemberHandler, filters
)
import database  # Tu archivo database.py con httpx

# Configuración de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Variables de entorno y seguridad
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SECRET_TOKEN = os.getenv("SECRET_TOKEN")
ADMIN_ID = 1011479473

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN no está definido.")
if not SECRET_TOKEN:
    raise ValueError("❌ SECRET_TOKEN no está definido.")

# -----------------------------------
# Comandos del bot
# -----------------------------------

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
    propuestas = await database.obtener_propuestas()
    if not propuestas:
        return await update.message.reply_text("No hay propuestas aún.")
    mensaje = "📋 *Propuestas actuales:*\n"
    for p in propuestas:
        mensaje += f"#{p['id']}: {p['texto']} (👤 {p['nombre_autor']}, 👍 {p['votos']})\n"
    await update.message.reply_text(mensaje.strip(), parse_mode="Markdown")

async def votar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Uso: /votar <id>")
    pid = int(context.args[0])
    uid = update.effective_user.id
    respuesta = await database.votar_por_propuesta(pid, uid)
    await update.message.reply_text(respuesta)

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_propuestas = await database.obtener_top_propuestas()
    if not top_propuestas:
        return await update.message.reply_text("No hay propuestas aún.")
    mensaje = "🏆 *Top propuestas:*\n"
    for p in top_propuestas:
        mensaje += f"#{p['id']}: {p['texto']} (👍 {p['votos']})\n"
    await update.message.reply_text(mensaje.strip(), parse_mode="Markdown")

async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Uso: /borrar <id>")
    pid = int(context.args[0])
    uid = update.effective_user.id
    respuesta = await database.borrar_propuesta(pid, uid)
    await update.message.reply_text(respuesta)

async def participacion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    participacion = await database.obtener_participacion()
    if not participacion:
        return await update.message.reply_text("Nadie ha participado aún.")
    mensaje = "📊 *Participación:*\n"
    for p in participacion:
        member = await context.bot.get_chat_member(update.effective_chat.id, p["uid"])
        nombre = member.user.first_name or "Usuario"
        mensaje += f"{nombre}: {p['count']} propuestas\n"
    await update.message.reply_text(mensaje.strip(), parse_mode="Markdown")

async def reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Solo el admin puede usar este comando.")
    await database.reiniciar_datos()
    await update.message.reply_text("🔄 Datos reiniciados. ¡Nueva ronda!")

# -----------------------------------
# Eventos de grupo
# -----------------------------------

async def saludo_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member.new_chat_member.status == "member":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="¡Gracias por invitarme! Usa /ayuda para empezar."
        )

async def bienvenida_nuevos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for nuevo in update.message.new_chat_members:
        await update.message.reply_text(f"👋 ¡Bienvenido/a {nuevo.first_name}!")

# -----------------------------------
# Configuración de FastAPI y Telegram
# -----------------------------------

app = FastAPI()
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Handlers de comandos
comandos = {
    "ayuda": ayuda, "proponer": proponer, "verpropuestas": verpropuestas,
    "votar": votar, "top": top, "borrar": borrar,
    "participacion": participacion_cmd, "reiniciar": reiniciar
}
for nombre, handler in comandos.items():
    bot_app.add_handler(CommandHandler(nombre, handler))

# Handlers de eventos de grupo
bot_app.add_handler(ChatMemberHandler(saludo_grupo, ChatMemberHandler.MY_CHAT_MEMBER))
bot_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bienvenida_nuevos))

# Endpoint del webhook
@app.post("/webhook")
async def telegram_webhook(
    req: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    if x_telegram_bot_api_secret_token != SECRET_TOKEN:
        logging.warning("⚠️ Acceso no autorizado al webhook.")
        raise HTTPException(status_code=403, detail="Token inválido")

    data = await req.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}

@app.get("/")
async def root():
    return JSONResponse({"status": "Bot en funcionamiento 🚀"})

# Eventos de inicio y apagado
@app.on_event("startup")
async def on_startup():
    await bot_app.initialize()
    webhook_url = "https://bot-telegram-seo.onrender.com/webhook"
    await bot_app.bot.set_webhook(
        url=webhook_url,
        secret_token=SECRET_TOKEN
    )
    logging.info(f"✅ Webhook registrado automáticamente en: {webhook_url}")

@app.on_event("shutdown")
async def on_shutdown():
    await bot_app.shutdown()
