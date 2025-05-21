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

# Token del bot (usa variable de entorno si es posible)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7545362589:AAGIrhr7ESef1Rt9xmt_Zv4Qw9wPqjjRvvE")

# Diccionarios globales para propuestas y votos
propuestas = {}
votos = defaultdict(set)
participacion = defaultdict(int)
propuesta_id = 1


# Función de ayuda
async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "🤖 *Comandos disponibles:*\n"
            "/proponer <texto> - Propón una idea\n"
            "/verpropuestas - Ver todas las propuestas\n"
            "/votar <id> - Vota por una propuesta\n"
            "/top - Ver propuestas más votadas\n"
            "/borrar <id> - Borra tu propuesta\n"
            "/participacion - Ver participación del grupo"
        ),
        parse_mode="Markdown"
    )


# Función para proponer
async def proponer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global propuesta_id
    if not context.args:
        await update.message.reply_text("Debes escribir una propuesta. Ej: /proponer Hacer un sorteo")
        return

    propuesta_texto = " ".join(context.args)
    propuestas[propuesta_id] = {
        "texto": propuesta_texto,
        "autor": update.effective_user.id,
        "nombre_autor": update.effective_user.first_name,
        "votos": 0
    }
    participacion[update.effective_user.id] += 1

    await update.message.reply_text(f"✅ Propuesta #{propuesta_id} registrada:\n\"{propuesta_texto}\"")
    propuesta_id += 1


# Función para ver todas las propuestas
async def verpropuestas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not propuestas:
        await update.message.reply_text("No hay propuestas aún.")
        return

    mensaje = "*📋 Propuestas actuales:*\n"
    for pid, datos in propuestas.items():
        mensaje += f"#{pid}: {datos['texto']} (👤 {datos['nombre_autor']}, 👍 {datos['votos']})\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")


# Función para votar
async def votar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Uso correcto: /votar <id>")
        return

    pid = int(context.args[0])
    uid = update.effective_user.id

    if pid not in propuestas:
        await update.message.reply_text("❌ La propuesta no existe.")
        return
    if uid in votos[pid]:
        await update.message.reply_text("⚠️ Ya has votado por esta propuesta.")
        return

    votos[pid].add(uid)
    propuestas[pid]["votos"] += 1
    await update.message.reply_text("✅ ¡Voto registrado!")


# Función para mostrar top de propuestas
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not propuestas:
        await update.message.reply_text("No hay propuestas aún.")
        return

    top_ordenado = sorted(propuestas.items(), key=lambda x: x[1]["votos"], reverse=True)
    mensaje = "*🏆 Propuestas más votadas:*\n"
    for pid, datos in top_ordenado[:5]:
        mensaje += f"#{pid}: {datos['texto']} (👍 {datos['votos']})\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")


# Función para borrar propuesta propia
async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Uso correcto: /borrar <id>")
        return

    pid = int(context.args[0])
    uid = update.effective_user.id

    if pid not in propuestas:
        await update.message.reply_text("❌ No existe esa propuesta.")
        return
    if propuestas[pid]["autor"] != uid:
        await update.message.reply_text("⚠️ Solo el autor puede borrar su propuesta.")
        return

    del propuestas[pid]
    if pid in votos:
        del votos[pid]
    await update.message.reply_text(f"🗑️ Propuesta #{pid} borrada.")


# Función para mostrar participación
async def participacion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not participacion:
        await update.message.reply_text("Nadie ha participado aún.")
        return

    mensaje = "*📊 Participación:*\n"
    for uid, count in participacion.items():
        nombre = (await context.bot.get_chat_member(update.effective_chat.id, uid)).user.first_name
        mensaje += f"{nombre}: {count} propuestas\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")


# Función de saludo al ser añadido al grupo
async def saludo_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member and update.my_chat_member.new_chat_member.status == "member":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="¡Gracias por agregarme al grupo! 🎉 Usa /ayuda para ver qué puedo hacer."
        )


# Función para dar la bienvenida a nuevos usuarios
async def bienvenida_nuevos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for miembro in update.message.new_chat_members:
        await update.message.reply_text(f"👋 ¡Bienvenido/a {miembro.first_name} al grupo!")


# --- Configuración de FastAPI y Telegram bot ---
app = FastAPI()
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Handlers de comandos
bot_app.add_handler(CommandHandler("ayuda", ayuda))
bot_app.add_handler(CommandHandler("proponer", proponer))
bot_app.add_handler(CommandHandler("verpropuestas", verpropuestas))
bot_app.add_handler(CommandHandler("votar", votar))
bot_app.add_handler(CommandHandler("top", top))
bot_app.add_handler(CommandHandler("borrar", borrar))
bot_app.add_handler(CommandHandler("participacion", participacion_cmd))

# Handlers de eventos de grupo
bot_app.add_handler(ChatMemberHandler(saludo_grupo, ChatMemberHandler.MY_CHAT_MEMBER))
bot_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bienvenida_nuevos))

# Webhook para recibir actualizaciones desde Telegram
@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}
