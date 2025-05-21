import logging
from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)
from collections import defaultdict

# Configura logging para depurar errores fácilmente
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

# Token de tu bot
import os
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Almacenes en memoria (se puede sustituir por DB en futuro)
propuestas = {}
votos = defaultdict(set)
participacion = defaultdict(int)
propuesta_id = 1


### SALUDO al ser agregado
async def saludo_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = update.my_chat_member.new_chat_member.status
    if status == "member":
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text="👋 ¡Hola grupo! Soy el bot de herramientas SEO. Escribe /ayuda para ver lo que puedo hacer."
        )

### BIENVENIDA a nuevos miembros
async def bienvenida_nuevos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        if not user.is_bot:
            participacion[user.id] += 1
            await update.message.reply_text(
                f"👋 ¡Bienvenido/a, {user.first_name}! Este es el grupo para compartir y conseguir herramientas SEO útiles."
            )

### COMANDO /ayuda
async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Comandos disponibles:\n"
        "/proponer [nombre] – Proponer nuevo plugin o herramienta\n"
        "/verpropuestas – Ver ideas propuestas\n"
        "/votar [ID] – Votar por una propuesta\n"
        "/top – Ver las más votadas\n"
        "/participacion – Ver ranking de actividad"
    )

### COMANDO /proponer
async def proponer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global propuesta_id
    args = context.args
    if not args:
        await update.message.reply_text("❗ Usa: /proponer Nombre del plugin [enlace opcional]")
        return
    texto = " ".join(args)
    propuestas[propuesta_id] = {"texto": texto, "autor": update.effective_user.first_name, "votos": 0, "link": ""}
    await update.message.reply_text(f"✅ Propuesta #{propuesta_id} guardada: {texto}")
    propuesta_id += 1
    participacion[update.effective_user.id] += 1

### COMANDO /verpropuestas
async def verpropuestas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not propuestas:
        await update.message.reply_text("⚠️ Aún no hay propuestas.")
        return
    msg = "\n".join([f"{pid}: {data['texto']} (Votos: {data['votos']})" for pid, data in propuestas.items()])
    await update.message.reply_text("📋 Propuestas:\n" + msg)

### COMANDO /votar
async def votar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❗ Usa: /votar [ID de la propuesta]")
        return
    try:
        pid = int(context.args[0])
        if pid not in propuestas:
            await update.message.reply_text("❌ Propuesta no encontrada.")
            return
        if user_id in votos[pid]:
            await update.message.reply_text("⚠️ Ya votaste por esta propuesta.")
            return
        propuestas[pid]["votos"] += 1
        votos[pid].add(user_id)
        participacion[user_id] += 1
        await update.message.reply_text(f"🗳️ ¡Voto registrado para la propuesta #{pid}!")
    except ValueError:
        await update.message.reply_text("⚠️ ID inválido.")

### COMANDO /top
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not propuestas:
        await update.message.reply_text("⚠️ No hay propuestas aún.")
        return
    ordenadas = sorted(propuestas.items(), key=lambda x: x[1]['votos'], reverse=True)
    top_msg = "\n".join([f"{pid}: {data['texto']} ({data['votos']} votos)" for pid, data in ordenadas[:5]])
    await update.message.reply_text("🏆 Top propuestas:\n" + top_msg)

### COMANDO /borrar (solo admin)
async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    member = await update.effective_chat.get_member(user.id)
    if not member.status in ["administrator", "creator"]:
        await update.message.reply_text("🚫 Solo los administradores pueden borrar propuestas.")
        return
    if not context.args:
        await update.message.reply_text("❗ Usa: /borrar [ID de la propuesta]")
        return
    try:
        pid = int(context.args[0])
        if pid in propuestas:
            del propuestas[pid]
            await update.message.reply_text(f"🗑️ Propuesta #{pid} eliminada.")
        else:
            await update.message.reply_text("⚠️ ID no encontrado.")
    except ValueError:
        await update.message.reply_text("⚠️ ID inválido.")

### COMANDO /participacion
async def participacion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not participacion:
        await update.message.reply_text("⚠️ Sin datos aún.")
        return
    top_users = sorted(participacion.items(), key=lambda x: x[1], reverse=True)
    msg = "📈 Ranking de participación:\n"
    for uid, count in top_users[:5]:
        user = await context.bot.get_chat_member(update.effective_chat.id, uid)
        msg += f"{user.user.first_name}: {count} acciones\n"
    await update.message.reply_text(msg)

### MAIN
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(ChatMemberHandler(saludo_grupo, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bienvenida_nuevos))

    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("proponer", proponer))
    app.add_handler(CommandHandler("verpropuestas", verpropuestas))
    app.add_handler(CommandHandler("votar", votar))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("borrar", borrar))
    app.add_handler(CommandHandler("participacion", participacion_cmd))

    print("🤖 Bot corriendo...")
    app.run_polling()
