import telegram.error
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    PicklePersistence, MessageHandler, filters
)
from telegram import Update, InlineKeyboardButton
from dotenv import load_dotenv
from bs4 import BeautifulSoup

from functools import wraps
from logging import handlers
import logging
import os
import requests

import settings
import job_queue

logging.getLogger('httpx').setLevel(logging.WARNING)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

bot_logger = logging.getLogger("bot_logger")
bot_logger.setLevel(logging.INFO)
file_handler = handlers.RotatingFileHandler(filename="../misc/logs/main.log",
                                            maxBytes=1024, backupCount=1)
bot_logger.addHandler(file_handler)


CHANGE_SETTINGS, LIST_LAST_CHECKS = range(2)


def send_action(action):
    """Sends `action` while processing func command."""

    def decorator(func):
        @wraps(func)
        async def command_func(update, context, *args, **kwargs):
            await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=action)
            return await func(update, context, *args, **kwargs)

        return command_func

    return decorator


# noinspection GrazieInspection
async def set_data(app: Application):
    """
    {
        "apps": {
                "1": {
                        "app_name": nome dell'app,
                        "app_link": link al Play Store
                        "current_version": ultima versione rilevata
                        "last_check_time": data e ora dell'ultimo controllo (serve in caso di arresti anomali)
                        "check_interval": intervallo tra due check
                        "send_on_check": manda un messaggio anche se non è stato trovato un nuovo aggiornamento
                    },
                ...
            },
        "settings": {
                "default_check_interval": intervallo di default tra 2 check,
                "default_send_on_check": manda un messaggio anche se non è stato trovato un nuovo aggiornamento default
                "tutorial": primo avvio
            },
        "last_checks":{
                "1": {
                    "last_check_time": data ultimo check
                },
                ...
            }
    }
    """

    if "apps" not in app.bot_data:
        app.bot_data["apps"] = {}
    if "settings" not in app.bot_data:
        app.bot_data["settings"] = {
            "default_check_interval": {
                "timedelta": None,
                "input": None
            },
            "default_send_on_check": None,
            "tutorial": False
        }
    if "last_checks" not in app.bot_data:
        app.bot_data["last_checks"] = {}


async def get_app_name_with_link(link: str):
    res = requests.get(link)
    if res.status_code != 200:
        bot_logger.warning(f"Not able to gather link {link}")
        return None
    name = BeautifulSoup(res.text, "html.parser").find('h1', itemprop='name')
    return name.get_text() if name else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != int(os.getenv("ADMIN_ID")) and update.effective_user.id != int(os.getenv("MY_ID")):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ You are not allowed to use this bot.")
        return

    if update.callback_query is not None:
        if len(li := update.callback_query.data.split(" ")) > 1:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id,
                                                 message_id=int(li[1]))
            except telegram.error.BadRequest:
                pass

    if context.bot_data["settings"]["tutorial"] is False:
        await context.bot.send_chat_action(action=ChatAction.TYPING, chat_id=update.effective_chat.id)
        keyboard = [
            [InlineKeyboardButton(text="🆘 Tutorial", callback_data="print_tutorial {}")],
            [InlineKeyboardButton(text="⏭ Procedi – Settaggio Valori Default", callback_data="set_defaults {}")],
        ]

        context.job_queue.run_once(callback=job_queue.scheduled_send_message,
                                   data={
                                       "chat_id": update.effective_chat.id,
                                       "text": "Prima di cominciare ad usare questo bot, vuoi un breve tutorial sul suo"
                                               " funzionamento generale?\n\n@AleLntr dice che è consigliabile 😊",
                                       "keyboard": keyboard,
                                       "web_preview": False,
                                       "close_button": [[1, 1], [2, 1]]
                                   },
                                   when=1)
        return 0

    await send_menu(update, context)


@send_action(ChatAction.TYPING)
async def tutorial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data["settings"]["tutorial"] = True
    if update.callback_query.data.startswith("print_tutorial"):
        text = ("💡 <b>Informazioni Generali</b>\n\n"
                "1️⃣ <b>Al Primo Avvio</b>\n"
                "Vengono settate tutte le variabili permanenti, utili al funzionamento del bot (impostazioni e valori"
                " di default). Da ora, <b>tutti</b> i dati verranno salvati all'interno di queste variabili permanenti "
                "e i valori contenuti all'interno saranno salvati, ad intervalli regolari, all'interno di un file "
                "chiamato <code>persistence</code> (è un file senza estensione contenente caratteri non leggibili)."
                "\n\n⚠️ Il salvataggio di tali informazioni sul file <code>persistence</code> serve per garantire che "
                "i dati non vengano persi in caso di arresti anomali dello script del bot. <u>La rimozione di tale "
                "file, pertanto, comporta la cancellazione della sua memoria</u>.\n\n"
                "Al primo avvio, ti verrà poi richiesto di impostare alcuni valori di default: l'<b>intervallo di check"
                " di default</b> – se non viene impostato per una certa applicazione – e il <b>parametro sulla "
                "condizione di invio del messaggio</b>, di default, che specifica se il messaggio andrà mandato solo"
                " se viene rilevato un aggiornamento oppure ad ogni controllo.\n\n"
                "2️⃣ <b>Impostazioni</b> – Il bot consente alcune semplici operazioni, tra cui:"
                "\n\n🔸 <b>Aggiunta di applicazioni da monitorare</b>\n L'aggiunta di un'applicazione può essere fatta "
                "tramite ricerca per nome o tramite il passaggio del link al Play Store."
                "\n\n🔸 <b>Settaggio delle applicazioni</b>\nQuando un'applicazione viene aggiunta, è richiesta "
                "l'impostazione di alcuni parametri, tra cui l'intervallo di check degli aggiornamenti e se il"
                " messaggio andrà mandato solo quando si trova un aggiornamento, oppure ad ogni controllo."
                "\n\n🔸 <b>Modifica delle impostazioni di app già aggiunte</b>\nDa un apposito menu, sarà possibile "
                "cambiare le impostazioni relative ad un'applicazione precedentemente aggiunta."
                "\n\n🔸 <b>Sospensione o rimozione di un'applicazione</b>\nPotrai anche sospendere gli aggiornamenti e "
                "riattivarli in un secondo momento, o rimuovere un'applicazione dall'elenco di quelle tracciate.\n\n"
                "➡ <b>Nota Importante</b> – Per consentire al bot di inviarti messaggi, ricordati di mantenere la chat "
                "attiva mantenendovi almeno un messaggio all'interno, altrimenti il bot non ti potrà scrivere.")
        keyboard = [
            [InlineKeyboardButton(text="⏭ Procedi – Settaggio Valori Default", callback_data="set_defaults {}")]
        ]

        context.job_queue.run_once(callback=job_queue.scheduled_send_message,
                                   data={
                                       "chat_id": update.effective_chat.id,
                                       "message_id": update.callback_query.data.split(" ")[1],
                                       "text": text,
                                       "keyboard": keyboard,
                                       "close_button": [1, 1]
                                   },
                                   when=1.5)
    return 1


@send_action(ChatAction.TYPING)
async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query is not None:
        if len(li := update.callback_query.data.split(" ")) > 1:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id,
                                                 message_id=int(li[1]))
            except telegram.error.BadRequest:
                pass
    keyboard = [
        [
            InlineKeyboardButton(text="⚙ Settings", callback_data="settings"),
            InlineKeyboardButton(text="📄 List Last Checks", callback_data="last_checks")
        ],
        [
            InlineKeyboardButton(text="🔐 Close Menu", callback_data="close_menu {}")
        ]
    ]

    context.job_queue.run_once(callback=job_queue.scheduled_send_message,
                               data={
                                   "chat_id": update.effective_chat.id,
                                   "text": "🔹 Ciao ҒŁҴҠӖҲ!\n\nSono il bot che controlla gli "
                                           "aggiornamenti delle applicazioni sul Play Store.\n\nScegli un'opzione ⬇",
                                   "keyboard": keyboard,
                                   "close_button": [2, 1]
                               },
                               when=1)


def main():
    persistence = PicklePersistence(filepath="../config/persistence")
    app = (ApplicationBuilder().token(os.getenv("BOT_TOKEN")).persistence(persistence).
           post_init(set_data).build())

    conv_handler1 = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            0: [
                CallbackQueryHandler(pattern="^print_tutorial.+$", callback=tutorial),
                CallbackQueryHandler(pattern="^set_defaults.+$", callback=settings.set_defaults)
            ],
            1: [
                CallbackQueryHandler(pattern="^set_defaults.+$", callback=settings.set_defaults)
            ],
            2: [
                MessageHandler(filters=filters.TEXT, callback=settings.set_defaults),
                CallbackQueryHandler(pattern="^interval_incorrect.+$", callback=settings.set_defaults),
                CallbackQueryHandler(pattern="^interval_correct.+$", callback=settings.set_defaults)
            ],
            3: [
                CallbackQueryHandler(pattern="^default_send_on_check_true.+$", callback=settings.set_defaults),
                CallbackQueryHandler(pattern="^default_send_on_check_false.+$", callback=settings.set_defaults)
            ]
        },
        fallbacks=[],
        name="default_settings_conv_handler",
        persistent=True
    )

    conv_handler2 = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(pattern="^default_setting_finished.+$", callback=start),
        ],
        states={
            CHANGE_SETTINGS: [],
            LIST_LAST_CHECKS: []
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler1)
    app.add_handler(conv_handler2)

    app.run_polling()


if __name__ == '__main__':
    load_dotenv()
    main()
