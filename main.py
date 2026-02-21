import os
import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from mcrcon import MCRcon
from dotenv import load_dotenv

# --------------------
# Загружаем .env
# --------------------
load_dotenv()

# --------------------
# Логирование
# --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# --------------------
# Читаем настройки из ENV
# --------------------
TOKEN = os.getenv("TELEGRAM_TOKEN")
RCON_HOST = os.getenv("RCON_HOST")
RCON_PORT = int(os.getenv("RCON_PORT", "25575"))
RCON_PASS = os.getenv("RCON_PASS")

# список чатов через запятую в .env
ALLOWED_CHATS = {
    int(x.strip())
    for x in os.getenv("ALLOWED_CHATS", "").split(",")
    if x.strip()
}

# Проверка обязательных переменных
required = [TOKEN, RCON_HOST, RCON_PASS]
if not all(required):
    raise RuntimeError("❌ Не заполнены переменные окружения (.env)")

# --------------------
# Декоратор проверки чата
# --------------------
def allowed_chat(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if ALLOWED_CHATS and update.effective_chat.id not in ALLOWED_CHATS:
            return
        await func(update, context)
    return wrapper

# --------------------
# RCON helpers
# --------------------
def get_online_players():
    try:
        with MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT) as m:
            res = m.command("list")

        if ": " in res:
            players = res.split(": ")[1].strip()
            if not players:
                return None
            return "\n".join(p.strip() for p in players.split(",") if p.strip())

        return "Не удалось получить список игроков"

    except Exception as e:
        logging.warning(f"RCON ошибка: {e}")
        return "Ошибка подключения к серверу"

# --------------------
# Команды
# --------------------
@allowed_chat
async def online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    players = get_online_players()

    if not players:
        await update.message.reply_text("На сервере никого нет")
    elif players.startswith("Ошибка") or players.startswith("Не удалось"):
        await update.message.reply_text(players)
    else:
        await update.message.reply_text(f"Игроки онлайн:\n\n{players}")


@allowed_chat
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")


@allowed_chat
async def restart_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT) as m:
            m.command("save-all")
            m.command("say Перезапуск сервера через Telegram")
            await update.message.reply_text("Сохраняю мир...")
            await asyncio.sleep(10)
            m.command("stop")

        logging.info("Сервер перезапущен через Telegram")
        await update.message.reply_text("Сервер перезагружается")

    except Exception as e:
        logging.warning(f"Ошибка restart: {e}")
        await update.message.reply_text("Ошибка при перезапуске")


@allowed_chat
async def say(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("Использование: /say <сообщение>")
        return

    msg = " ".join(context.args)

    try:
        with MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT) as m:
            m.command(f"say {msg}")

        logging.info(f"Say: {msg}")
        await update.message.reply_text("Отправлено")

    except Exception as e:
        logging.warning(f"Ошибка say: {e}")
        await update.message.reply_text("Ошибка отправки")


@allowed_chat
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("Использование: /kick <ник> [причина]")
        return

    player = context.args[0]
    reason = " ".join(context.args[1:]) or "Кик через Telegram"

    try:
        with MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT) as m:
            res = m.command(f"kick {player} {reason}")   # ← сохраняем ответ

        logging.info(f"Kick: {player} ({reason}) | response: {res}")

        if res and "no player was found" in res.lower():
            await update.message.reply_text(f"Игрок {player} не найден")
        else:
            await update.message.reply_text(f"{player} кикнут")

    except Exception as e:
        logging.warning(f"Ошибка kick: {e}")
        await update.message.reply_text("Ошибка кика")


@allowed_chat
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


# --------------------
# Запуск
# --------------------
if __name__ == "__main__":

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("online", online))
    app.add_handler(CommandHandler("getid", get_chat_id))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("restart", restart_server))
    app.add_handler(CommandHandler("say", say))
    app.add_handler(CommandHandler("kick", kick))

    logging.info("MPCraft Bot запущен")
    app.run_polling()
