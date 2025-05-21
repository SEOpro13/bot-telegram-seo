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
from database import (
    propuestas, votos, participacion, get_propuesta_id,
    guardar_datos, borrar_propuesta, registrar_propuesta, votar_por_propuesta
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7545362589:AAGIrhr7ESef1Rt9xmt_Zv4Qw9wPqjjRvvE")
ADMIN_ID = 1011479473

# === COMANDOS ===

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Comandos disponibles:*\n"
        "/proponer <texto> - Propón una idea\n"
        "/verpropuestas - Ver todas las propuestas\n"
        "/votar <id> - Vota por una propuesta\n"
        "/top - Ver propuestas más votadas\n"
        "/borrar <id> - Borra tu propuesta\n"
        "/participacion - Ver participación del grupo\n"
        "/reiniciar - Reiniciar todo (solo admin)",
        parse_mode="Markdown"
    )

async def proponer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Debes escribir una propuesta. Ej: /proponer Hacer un sorteo")
        return

    texto = " ".join(context.args)
    pid = registrar_propuesta(texto, update.effective_user)
    await update.message.reply_text(f"✅ Propuesta #{pid} registrada:\n\"{texto}\"")
    guardar_datos()

async def verpropuestas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not propuestas:
        await update.message.reply_text("No hay propuestas aún.")
        return

    mensaje = "*📋 Propuestas actuales:*\n"
    for pid, datos in propuestas.items():
        mensaje += f"#{pid}: {datos['texto']} (👤 {datos['nombre_autor']}, 👍 {datos['votos']})\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def votar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Uso correcto: /votar <id>")
        return

    pid = int(context.args[0])
    uid = update.effective_user.id

    resultado = votar_por_propuesta(pid, uid)
    await update.message.reply_text(resultado)
    guardar_datos()

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not propuestas:
        await update.message.reply_text("No hay propuestas aún.")
        return

    top_ordenado = sorted(propuestas.items(), key=lambda x: x[1]["votos"], reverse=True)
    mensaje = "*🏆 Propuestas más votadas:*\n"
    for pid, datos in top_ordenado[:5]:
        mensaje += f"#{pid}: {datos['texto']} (👍 {datos['votos']})\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Uso correcto: /borrar <id>")
        return

    pid = int(context.args[0])
    uid = update.effective_user.id
    resultado = borrar_propuesta(pid, uid)
    await update.message.reply_text(resultado)
    guardar_datos()

async def participacion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not participacion:
        await update.message.reply_text("Nadie ha participado aún.")
        return

    mensaje = "*📊 Participación:*\n"
    for uid, count in participacion.items():
        nombre = (await context.bot.get_chat_member(update.effective_chat.id, uid)).user.first_name
        mensaje += f"{nombre}: {count} propuestas\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ No tienes permisos para usar este comando.")
        return

    from database import reiniciar_datos
    reiniciar_datos()
    await update.message.reply_text("🗑️ Todos los datos han sido reiniciados. ¡Nueva ronda iniciada!")

async def saludo_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member and update.my_chat_member.new_chat_member.status == "member":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="¡Gracias por agregarme al grupo! 🎉 Usa /ayuda para ver qué puedo hacer."
        )

async def bienvenida_nuevos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for miembro in update.message.new_chat_members:
        await update.message.reply_text(f"👋 ¡Bienvenido/a {miembro.first_name} al grupo!")

# === FASTAPI y Telegram ===
app = FastAPI()
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Handlers
bot_app.add_handler(CommandHandler("ayuda", ayuda))
bot_app.add_handler(CommandHandler("proponer", proponer))
bot_app.add_handler(CommandHandler("verpropuestas", verpropuestas))
bot_app.add_handler(CommandHandler("votar", votar))
bot_app.add_handler(CommandHandler("top", top))
bot_app.add_handler(CommandHandler("borrar", borrar))
bot_app.add_handler(CommandHandler("participacion", participacion_cmd))
bot_app.add_handler(CommandHandler("reiniciar", reiniciar))
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
