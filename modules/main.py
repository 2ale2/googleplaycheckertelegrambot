import datetime
import logging
import os

import pytz
from logging import handlers

import telegram.error
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    Defaults, TypeHandler
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


CHANGE_SETTINGS, MENAGE_APPS, UNSUSPEND_APP, MENAGE_APPS_OPTIONS, LIST_APPS, ADD_APP = range(6)

SEND_LINK, CONFIRM_APP_NAME = range(2)

SET_INTERVAL, CONFIRM_INTERVAL, SEND_ON_CHECK, SET_UP_ENDED = range(4)

EDIT_SELECT_APP, EDIT_CONFIRM_APP = range(2)

DELETE_APP_SELECT, DELETE_APP_CONFIRM = range(2)


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
                "default_check_interval": {
                        "input": {
                                "months": mesi
                                "days": giorni
                                "hours": ore
                                "minutes": minuti
                                "seconds": secondi
                            },
                        "timedelta": timedelta dell'input
                    },
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
        li = []
        i = app.bot_data["apps"][ap]
        try:
            if i["next_check"] - datetime.datetime.now(pytz.timezone('Europe/Rome')) < datetime.timedelta(0):
                app.job_queue.run_once(callback=job_queue.scheduled_app_check,
                                       data={
                                           "app_id": i["app_id"],
                                           "app_link": i["app_link"],
                                           "app_index": ap
                                       },
                                       when=1,
                                       name=i["app_name"])
                app.job_queue.run_repeating(callback=job_queue.scheduled_app_check,
                                            interval=i["check_interval"]["timedelta"],
                                            data={
                                                "app_id": i["app_id"],
                                                "app_link": i["app_link"],
                                                "app_index": ap
                                            },
                                            name=i["app_name"])
            else:
                app.job_queue.run_once(callback=job_queue.scheduled_app_check,
                                       data={
                                           "app_id": i["app_id"],
                                           "app_link": i["app_link"],
                                           "app_index": ap
                                       },
                                       when=i["next_check"],
                                       name=i["app_name"])
                app.job_queue.run_repeating(callback=job_queue.scheduled_app_check,
                                            interval=i["check_interval"]["timedelta"],
                                            data={
                                                "app_id": i["app_id"],
                                                "app_link": i["app_link"],
                                                "app_index": ap
                                            },
                                            first=i["next_check"] + i["check_interval"]["timedelta"],
                                            name=i["app_name"])
        except KeyError:
            li.append(ap)

        for i in li:
            del app.bot_data["apps"][i]


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
                "Sono in grado di controllare periodicamente la presenza di aggiornamenti relativi ad applicazioni sul "
                "Play Store. Per funzionare, ho bisogno di tre informazioni:\n"
                "  1. il <u>link all'applicazione</u> che ti interessa;\n"
                "  2. l'<u>intervallo di controllo</u> tra due check;\n"
                "  3. in quali <u>condizioni</u> vuoi ricevere il messaggio.\n\n"
                "ℹ <b>Verrai guidato in ogni passaggio.</b> In caso di problemi, contatta @AleLntr."
                "1️⃣ <b>Al Primo Avvio</b>\n"
                "Vengono settate le impostazioni di default, utili al mio funzionamento. Da ora, <b>tutti</b> i dati "
                "verranno salvati all'interno di alcune variabili permanenti."
                "I valori contenuti all'interno di queste variabili saranno salvati, ad intervalli regolari, "
                "all'interno di un file chiamato <code>persistence</code> (è un file senza estensione contenente "
                "caratteri non leggibili).\n\n"
                "⚠️ Il salvataggio di tali informazioni sul file <code>persistence</code> serve per garantire che "
                "i dati non vengano persi in caso di arresti anomali dello script del bot. <u>La rimozione di tale "
                "file, pertanto, comporta la cancellazione della sua memoria</u> e, in tal caso, il bot dovrà "
                "essere reimpostato, come ti attingi a fare.\n\n"
                "I valori che stai per impostare costituiscono le <b>impostazioni di default</b>: l'<b>intervallo di "
                "check di default</b> – se non viene impostato per una certa applicazione – e il <b>parametro sulla "
                "condizione di invio del messaggio</b>, di default, che specifica se il messaggio andrà mandato solo"
                " se viene rilevato un aggiornamento oppure ad ogni controllo.\n\n"
                "2️⃣ <b>Impostazioni</b> – Il bot consente alcune semplici operazioni, tra cui:"
                "\n\n🔸 <b>Aggiunta di applicazioni da monitorare</b>\n  L'aggiunta di un'applicazione può essere fatta"
                " tramite il passaggio del link al Play Store."
                "\n\n🔸 <b>Settaggio delle applicazioni</b>\n  Quando un'applicazione viene aggiunta, è richiesta "
                "l'impostazione di controllo."
                "\n\n🔸 <b>Modifica delle impostazioni di app già aggiunte</b>\n  Da un apposito menu, sarà possibile "
                "cambiare le impostazioni relative ad un'applicazione precedentemente aggiunta."
                "\n\n🔸 <b>Sospensione o rimozione di un'applicazione</b>\n  Potrai anche sospendere gli aggiornamenti"
                " e riattivarli in un secondo momento, o rimuovere un'applicazione dall'elenco di quelle tracciate."
                "\n\n🔸 <b>Modifica delle impostazioni di Default</b>\n  Tutti i valori possono essere cambiati tramite "
                "le impostazioni.\n\n"
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

    text = ("🔹 Ciao ҒŁҴҠӖҲ!\n\nSono il bot che controlla gli aggiornamenti delle applicazioni sul Play Store.\n\n"
            "Scegli un'opzione ⬇")
    if update.callback_query and update.callback_query.data == "back_to_main_menu":
        await settings.parse_conversation_message(context=context,
                                                  data={
                                                      "chat_id": update.effective_chat.id,
                                                      "text": text,
                                                      "reply_markup": InlineKeyboardMarkup(keyboard),
                                                      "message_id": update.effective_message.message_id
                                                  })
    else:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        context.job_queue.run_once(callback=job_queue.scheduled_send_message,
                                   data={
                                       "chat_id": update.effective_chat.id,
                                       "text": text,
                                       "keyboard": keyboard,
                                       "close_button": [2, 1]
                                   },
                                   when=1)

    return CHANGE_SETTINGS


async def catch_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query and ("settings" in update.callback_query.data):
        print(update.callback_query.data)
        for h in context.application.handlers:
            for j in context.application.handlers[h]:
                if isinstance(j, ConversationHandler):
                    for i in j.entry_points:
                        if hasattr(i, "pattern"):
                            print(i.pattern)
                        print(i.check_update(update))
                    for i in j.states:
                        for li in j.states[i]:
                            if isinstance(li, ConversationHandler):
                                for i1 in li.entry_points:
                                    if hasattr(i1, "pattern"):
                                        print(i1.pattern)
                                    if i1.check_update(update):
                                        print(i1.check_update(update))
                                for i1 in li.states:
                                    for li1 in li.states[i1]:
                                        if isinstance(li1, ConversationHandler):
                                            for i2 in li1.entry_points:
                                                if hasattr(i2, "pattern"):
                                                    print(i2.pattern)
                                                if i2.check_update(update):
                                                    print(i2.check_update(update))
                                            for i2 in li1.states:
                                                for li2 in li1.states[i2]:
                                                    if hasattr(li2, "pattern"):
                                                        print(li2.pattern)
                                                    if li2.check_update(update):
                                                        print(li2.check_update(update))
                                            for i2 in li1.fallbacks:
                                                if hasattr(i2, "pattern"):
                                                    print(i2.pattern)
                                                if i2.check_update(update):
                                                    print(i2.check_update(update))
                                        if hasattr(li1, "pattern"):
                                            print(li1.pattern)
                                        if li1.check_update(update):
                                            print(li1.check_update(update))
                                for i1 in li.fallbacks:
                                    if hasattr(i1, "pattern"):
                                        print(i1.pattern)
                                    if i1.check_update(update):
                                        print(i1.check_update(update))
                            if hasattr(li, "pattern"):
                                print(li.pattern)
                            if li.check_update(update):
                                print(li.check_update(update))
                    for i in j.fallbacks:
                        if hasattr(i, "pattern"):
                            print(i.pattern)
                        if i.check_update(update):
                            print(i.check_update(update))
                        return
                if hasattr(j, "pattern"):
                    print(j.pattern)
                if j.check_update(update):
                    print(j.check_update(update))


def main():
    persistence = PicklePersistence(filepath="../misc/config/persistence")
    app = (ApplicationBuilder().token(os.getenv("BOT_TOKEN")).persistence(persistence).
           defaults(Defaults(tzinfo=pytz.timezone('Europe/Rome'))).
           post_init(set_data).build())

    conv_handler1 = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(pattern="edit_default_settings", callback=settings.set_defaults)
        ],
        states={
            0: [
                CallbackQueryHandler(pattern="^print_tutorial.+$", callback=tutorial),
                CallbackQueryHandler(pattern="^set_defaults.+$", callback=settings.set_defaults),
                CallbackQueryHandler(pattern="^confirm_edit_default_settings.+$", callback=settings.set_defaults)
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
        fallbacks=[CallbackQueryHandler(pattern="cancel_edit_settings", callback=settings.change_settings)],
        name="default_settings_conv_handler"
    )

    add_app_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pattern="add_app", callback=settings.add_app)
        ],
        states={
            SEND_LINK: [
                MessageHandler(filters=filters.TEXT, callback=settings.add_app)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(pattern="back_to_settings", callback=settings.send_menage_apps_menu)
        ]
    )

    # set_app_conv_handler = ConversationHandler(
    #     entry_points=[
    #         CallbackQueryHandler(pattern="app_name_from_link_correct", callback=settings.set_app),
    #         CallbackQueryHandler(pattern="confirm_app_to_edit", callback=settings.set_app),
    #         CallbackQueryHandler(pattern="^edit_app_from_check.+$", callback=settings.set_app)
    #     ],
    #     states={
    #         SET_INTERVAL: [
    #             MessageHandler(filters.TEXT, callback=settings.set_app),
    #             CallbackQueryHandler(pattern="set_default_values", callback=settings.set_app),
    #             CallbackQueryHandler(pattern="edit_set_default_values", callback=settings.set_app)
    #         ],
    #         CONFIRM_INTERVAL: [
    #             CallbackQueryHandler(pattern="^interval_incorrect.+$", callback=settings.set_app),
    #             CallbackQueryHandler(pattern="^interval_correct.+$", callback=settings.set_app)
    #         ],
    #         SEND_ON_CHECK: [
    #             CallbackQueryHandler(pattern="send_on_check_true", callback=settings.set_app),
    #             CallbackQueryHandler(pattern="send_on_check_false", callback=settings.set_app)
    #         ],
    #     },
    #     fallbacks=[CallbackQueryHandler(pattern="^back_to_settings.+$", callback=settings.menage_apps)],
    #     allow_reentry=True
    # )
    #
    # add_app_conv_handler = ConversationHandler(
    #     entry_points=[CallbackQueryHandler(pattern="add_app", callback=settings.add_app)],
    #     states={
    #         SEND_LINK: [
    #             MessageHandler(filters=filters.TEXT, callback=settings.add_app),
    #         ],
    #         CONFIRM_APP_NAME: [
    #             set_app_conv_handler,
    #             CallbackQueryHandler(pattern="app_name_from_link_not_correct", callback=settings.add_app),
    #         ]
    #     },
    #     fallbacks=[CallbackQueryHandler(pattern="^back_to_settings.+$", callback=settings.menage_apps)],
    #     allow_reentry=True
    # )
    #
    # app_names = settings.create_edit_app_list(app.bot_data)
    #
    # edit_app_conv_handler = ConversationHandler(
    #     entry_points=[
    #         CallbackQueryHandler(pattern="edit_app", callback=settings.edit_app),
    #         CallbackQueryHandler(pattern="cancel_edit_app", callback=settings.edit_app)
    #     ],
    #     states={
    #         EDIT_SELECT_APP: [
    #             MessageHandler(filters.TEXT, callback=settings.edit_app),
    #             MessageHandler(filters.Text(strings=app_names), callback=settings.edit_app),
    #         ],
    #         EDIT_CONFIRM_APP: [
    #             set_app_conv_handler
    #         ]
    #     },
    #     fallbacks=[CallbackQueryHandler(pattern="back_settings", callback=settings.menage_apps)],
    #     allow_reentry=True
    # )
    #
    # delete_app_conv_handler = ConversationHandler(
    #     entry_points=[CallbackQueryHandler(pattern="delete_app", callback=settings.remove_app)],
    #     states={
    #         DELETE_APP_SELECT: [
    #             MessageHandler(filters.TEXT, callback=settings.remove_app)
    #         ],
    #         DELETE_APP_CONFIRM: [
    #             CallbackQueryHandler(pattern="^suspend_from_remove.+$", callback=settings.suspend_app),
    #             CallbackQueryHandler(pattern="cancel_remove", callback=settings.remove_app)
    #         ]
    #     },
    #     fallbacks=[
    #         CallbackQueryHandler(pattern="confirm_remove", callback=settings.remove_app),
    #         CallbackQueryHandler(pattern="^back_from_remove.+$", callback=settings.menage_apps)
    #     ]
    # )

    conv_handler2 = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pattern="settings", callback=settings.change_settings),
            CallbackQueryHandler(pattern="^default_setting_finished.+$", callback=send_menu)
        ],
        states={
            CHANGE_SETTINGS: [
                CallbackQueryHandler(pattern="menage_apps", callback=settings.menage_apps),
                conv_handler1,
                CallbackQueryHandler(pattern="back_to_main_menu", callback=send_menu)
            ],
            MENAGE_APPS: [
                add_app_conv_handler,
                # edit_app_conv_handler,
                # delete_app_conv_handler,
                CallbackQueryHandler(pattern="list_apps", callback=settings.list_apps),
                CallbackQueryHandler(pattern="unsuspend_app", callback=settings.suspend_app),
                CallbackQueryHandler(pattern="back_to_main_settings", callback=settings.menage_apps),
                CallbackQueryHandler(pattern="settings", callback=settings.change_settings)
            ],
            LIST_APPS: [
                CallbackQueryHandler(pattern="back_from_list", callback=settings.menage_apps)
            ],
            UNSUSPEND_APP: [
                CallbackQueryHandler(pattern="^unsuspend_app.+$", callback=settings.suspend_app),
                CallbackQueryHandler(pattern="^back_to_main_settings.+$", callback=settings.menage_apps)
            ]
        },
        fallbacks=[CallbackQueryHandler(pattern="list_app", callback=settings.list_apps)],
        allow_reentry=True
    )

    # app.add_handler(TypeHandler(Update, callback=catch_update), group=-1)

    app.add_handler(conv_handler1)
    app.add_handler(conv_handler2)
    # app.add_handler(set_app_conv_handler)
    app.add_handler(CallbackQueryHandler(pattern="^suspend_app.+$", callback=settings.suspend_app))
    app.add_handler(CallbackQueryHandler(pattern="^delete_message.+$",
                                         callback=settings.delete_extemporary_message))
    app.add_handler(CallbackQueryHandler(pattern="^edit_from_job.+$", callback=settings.see_app_settings))
    # app.add_handler(edit_app_conv_handler)

    app.run_polling()


if __name__ == '__main__':
    load_dotenv()
    main()
