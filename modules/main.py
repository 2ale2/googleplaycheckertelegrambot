import datetime
import logging
import os

import pytz
from logging import handlers

import telegram.error
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    PicklePersistence,
    MessageHandler,
    filters,
    Defaults
)

import job_queue
import settings
from decorators import send_action

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


CHANGE_SETTINGS, MENAGE_APPS, LIST_LAST_CHECKS, MENAGE_APPS_OPTIONS, LIST_APPS, ADD_APP = range(6)

SEND_LINK, CONFIRM_APP_NAME = range(2)

SET_INTERVAL, CONFIRM_INTERVAL, SEND_ON_CHECK, SET_UP_ENDED = range(4)

EDIT_SELECT_APP, EDIT_INTERVAL = range(2)


# noinspection GrazieInspection
async def set_data(app: Application):
    """
    {
        "apps": {
                "1": {
                        "app_name": nome dell'app
                        "app_id": id del pacchetto
                        "app_link": link al Play Store
                        "current_version": ultima versione rilevata
                        "last_check_time": data e ora dell'ultimo controllo (serve in caso di arresti anomali)
                        "check_interval": intervallo tra due check
                        "next_check": data e ora prossimo check
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

    for ap in app.bot_data["apps"]:
        i = app.bot_data["apps"][ap]
        if i["next_check"] - datetime.datetime.now(pytz.timezone('Europe/Rome')) < datetime.timedelta(0):
            app.job_queue.run_once(callback=job_queue.scheduled_app_check,
                                   data={
                                       "app_id": i["app_id"],
                                       "app_link": i["app_link"],
                                       "app_index": ap
                                   },
                                   when=1)
            app.job_queue.run_repeating(callback=job_queue.scheduled_app_check,
                                        interval=i["check_interval"]["timedelta"],
                                        data={
                                            "app_id": i["app_id"],
                                            "app_link": i["app_link"],
                                            "app_index": ap
                                        })
        else:
            app.job_queue.run_once(callback=job_queue.scheduled_app_check,
                                   data={
                                       "app_id": i["app_id"],
                                       "app_link": i["app_link"],
                                       "app_index": ap
                                   },
                                   when=i["next_check"])
            app.job_queue.run_repeating(callback=job_queue.scheduled_app_check,
                                        interval=i["check_interval"]["timedelta"],
                                        data={
                                            "app_id": i["app_id"],
                                            "app_link": i["app_link"],
                                            "app_index": ap
                                        },
                                        first=i["next_check"] + i["check_interval"]["timedelta"])


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
    return ConversationHandler.END


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

    return CHANGE_SETTINGS


def main():
    persistence = PicklePersistence(filepath="../misc/config/persistence")
    app = (ApplicationBuilder().token(os.getenv("BOT_TOKEN")).persistence(persistence).
           defaults(Defaults(tzinfo=pytz.timezone('Europe/Rome'))).
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

    set_new_app_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pattern="app_name_from_link_correct", callback=settings.set_app)
        ],
        states={
            SET_INTERVAL: [
                MessageHandler(filters.TEXT, callback=settings.set_app),
                CallbackQueryHandler(pattern="set_default_values", callback=settings.set_app)
            ],
            CONFIRM_INTERVAL: [
                CallbackQueryHandler(pattern="^interval_incorrect.+$", callback=settings.set_app),
                CallbackQueryHandler(pattern="^interval_correct.+$", callback=settings.set_app)
            ],
            SEND_ON_CHECK: [
                CallbackQueryHandler(pattern="send_on_check_true", callback=settings.set_app),
                CallbackQueryHandler(pattern="send_on_check_false", callback=settings.set_app)
            ],
            SET_UP_ENDED: [
                CallbackQueryHandler(pattern="add_app", callback=settings.add_app)
            ]
        },
        fallbacks=[CallbackQueryHandler(pattern="^back_to_main_settings.+$", callback=settings.menage_apps)],
        allow_reentry=True
    )

    add_app_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(pattern="add_app", callback=settings.add_app)],
        states={
            SEND_LINK: [
                MessageHandler(
                    filters=filters.TEXT, callback=settings.add_app),
            ],
            CONFIRM_APP_NAME: [
                set_new_app_conv_handler,
                CallbackQueryHandler(pattern="app_name_from_link_not_correct", callback=settings.add_app)
            ]
        },
        fallbacks=[CallbackQueryHandler(pattern="^back_to_main_settings.+$", callback=settings.menage_apps),
                   CallbackQueryHandler(pattern="app_name_from_link_correct", callback=settings.add_app)],
        allow_reentry=True
    )

    app_names = settings.create_edit_app_list(app.bot_data)

    edit_app_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pattern="edit_app", callback=settings.edit_app),
            CallbackQueryHandler(pattern="go_back_to_edit_app", callback=settings.edit_app)
        ],
        states={
            EDIT_SELECT_APP: [
                MessageHandler(filters.TEXT, callback=settings.edit_app),
                MessageHandler(filters.Text(strings=app_names), callback=settings.edit_app)
            ],
            EDIT_INTERVAL: [
                CallbackQueryHandler(pattern="set_default_values", callback=settings.edit_app)
            ]
        },
        fallbacks=[]
    )

    conv_handler2 = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pattern="settings", callback=settings.change_settings),
            CallbackQueryHandler(pattern="^default_setting_finished.+$", callback=send_menu)
        ],
        states={
            CHANGE_SETTINGS: [
                CallbackQueryHandler(pattern="settings", callback=settings.change_settings),
                CallbackQueryHandler(pattern="menage_apps", callback=settings.menage_apps),
                CallbackQueryHandler(pattern="edit_default_settings", callback=settings.edit_default_settings),
            ],
            MENAGE_APPS: [
                add_app_conv_handler,
                edit_app_conv_handler,
                CallbackQueryHandler(pattern="back_to_main_menu", callback=send_menu),
                CallbackQueryHandler(pattern="list_apps", callback=settings.menage_apps),
                CallbackQueryHandler(pattern="info_app", callback=settings.menage_apps),
                CallbackQueryHandler(pattern="remove_app", callback=settings.menage_apps)
            ],
            LIST_APPS: [
                CallbackQueryHandler(pattern="remove_app", callback=settings.menage_apps),
                CallbackQueryHandler(pattern="edit_app", callback=settings.menage_apps),
                CallbackQueryHandler(pattern="info_app", callback=settings.menage_apps),
                CallbackQueryHandler(pattern="^back_to_main_settings.+$", callback=settings.menage_apps)
            ],
            LIST_LAST_CHECKS: []
        },
        fallbacks=[],
        allow_reentry=True
    )

    app.add_handler(conv_handler1)
    app.add_handler(conv_handler2)
    app.add_handler(CallbackQueryHandler(pattern="^delete_check_message.+$",
                                         callback=settings.delete_callback_query_message))

    app.run_polling()


if __name__ == '__main__':
    load_dotenv()
    main()
