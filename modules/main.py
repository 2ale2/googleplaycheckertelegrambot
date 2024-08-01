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
from conv_states import ConversationState
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

    if "actions" not in app.bot_data:
        app.bot_data["actions"] = {
            "adding": False,
            "editing": False,
            "editing_from_check": False
        }

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

    if "editing" in app.bot_data:
        del app.bot_data["editing"]
    if "adding" in app.bot_data:
        del app.bot_data["adding"]
    if "removing" in app.bot_data:
        del app.bot_data["removing"]


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
                "ℹ <b>Verrai guidato in ogni passaggio.</b> In caso di problemi, contatta @AleLntr.\n\n"
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
                "2️⃣ <b>Funzioni</b> – Il bot consente alcune semplici operazioni, tra cui:"
                "\n\n🔸 <b>Aggiunta di applicazioni da monitorare</b>\nL'aggiunta di un'applicazione può essere fatta"
                " tramite il passaggio del link al Play Store."
                "\n\n🔸 <b>Settaggio delle applicazioni</b>\nQuando un'applicazione viene aggiunta, è richiesta "
                "l'impostazione di controllo."
                "\n\n🔸 <b>Modifica delle impostazioni di app già aggiunte</b>\nDa un apposito menu, sarà possibile "
                "cambiare le impostazioni relative ad un'applicazione precedentemente aggiunta."
                "\n\n🔸 <b>Sospensione o rimozione di un'applicazione</b>\nPotrai anche sospendere gli aggiornamenti"
                " e riattivarli in un secondo momento, o rimuovere un'applicazione dall'elenco di quelle tracciate."
                "\n\n🔸 <b>Modifica delle impostazioni di Default</b>\nTutti i valori possono essere cambiati tramite "
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

    return ConversationState.CHANGE_SETTINGS


async def explore_handlers(matches: list, handler_s, update, level=0):
    indent = ' ' * (level * 4)  # Create indentation for better readability
    for handler in handler_s:
        if isinstance(handler, ConversationHandler):
            print(f"{indent}Exploring ConversationHandler at level {level}")
            # Explore entry points
            for entry_point in handler.entry_points:
                if hasattr(entry_point, "pattern"):
                    print(f"{indent}Entry point pattern: {entry_point.pattern}")
                if entry_point.check_update(update):
                    print(f"{indent}Match found in entry point at level {level}")
                    matches.append(handler)

            # Recursively explore states
            for state in handler.states:
                print(f"{indent}Exploring state: {state}")
                await explore_handlers(matches, handler.states[state], update, level + 1)

            # Explore fallbacks
            for fallback in handler.fallbacks:
                if hasattr(fallback, "pattern"):
                    print(f"{indent}Fallback pattern: {fallback.pattern}")
                if fallback.check_update(update):
                    print(f"{indent}Match found in fallback at level {level}")
                    matches.append(handler)

        else:
            if hasattr(handler, "pattern"):
                print(f"{indent}Handler pattern: {handler.pattern}")
            if handler.check_update(update):
                print(f"{indent}Match found at level {level}")
                matches.append(handler)

    return matches


async def catch_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matched_handlers = []
    if update.callback_query and ("back_to_settings" in update.callback_query.data):
        print(update.callback_query.data)
        for handler_group in context.application.handlers.values():
            matched_handlers = await explore_handlers(matched_handlers, handler_group, update)
        if matched_handlers:
            print(f"Matched handlers: {matched_handlers}")
        else:
            print("No matching handler found")
        print("=====================================================")


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

    set_app_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pattern="app_name_from_link_correct", callback=settings.set_app),
            CallbackQueryHandler(pattern="confirm_app_to_edit", callback=settings.set_app),
            CallbackQueryHandler(pattern="^edit_app_from_check.+$", callback=settings.set_app)
        ],
        states={
            ConversationState.SET_INTERVAL: [
                MessageHandler(filters=filters.TEXT, callback=settings.set_app),
                CallbackQueryHandler(pattern="^set_default_values$", callback=settings.set_app),
                CallbackQueryHandler(pattern="^edit_set_default_values$", callback=settings.set_app)
            ],
            ConversationState.CONFIRM_INTERVAL: [
                CallbackQueryHandler(pattern="interval_correct", callback=settings.set_app),
                CallbackQueryHandler(pattern="interval_incorrect", callback=settings.set_app)
            ],
            ConversationState.SEND_ON_CHECK: [
                CallbackQueryHandler(pattern="^send_on_check.+$", callback=settings.set_app)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(pattern="^back_to_settings$", callback=settings.send_menage_apps_menu)
        ],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END
        }
    )

    add_app_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pattern="add_app", callback=settings.add_app)
        ],
        states={
            ConversationState.SEND_LINK: [
                MessageHandler(filters=filters.TEXT, callback=settings.add_app)
            ],
            ConversationState.CONFIRM_APP_NAME: [
                # set_app_conv_handler,
                CallbackQueryHandler(pattern="app_name_from_link_not_correct", callback=settings.add_app)
            ],
            ConversationState.ADD_OR_EDIT_FINISH: []
        },
        fallbacks=[
            CallbackQueryHandler(pattern="^back_to_settings$", callback=settings.send_menage_apps_menu)
        ],
        allow_reentry=True  # per consentire di aggiungere un'altra app
    )

    edit_app_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pattern="^edit_app$", callback=settings.edit_app)
        ],
        states={
            ConversationState.EDIT_SELECT_APP: [
                MessageHandler(filters.TEXT, callback=settings.edit_app)
            ],
            ConversationState.EDIT_CONFIRM_APP: [
                # set_app_conv_handler
            ],
            ConversationState.ADD_OR_EDIT_FINISH: []
        },
        fallbacks=[
            CallbackQueryHandler(pattern="^back_to_settings$", callback=settings.send_menage_apps_menu)
        ],
        allow_reentry=True  # per consentire di modificare un'altra app
    )

    delete_app_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pattern="delete_app", callback=settings.remove_app)
        ],
        states={
            ConversationState.DELETE_APP_SELECT: [
               MessageHandler(filters.TEXT, callback=settings.remove_app)
            ],
            ConversationState.DELETE_APP_CONFIRM: [
                CallbackQueryHandler(pattern="confirm_remove", callback=settings.remove_app),
                CallbackQueryHandler(pattern="cancel_remove", callback=settings.remove_app),
                CallbackQueryHandler(pattern="^suspend_from_remove.+$", callback=settings.remove_app)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(pattern="^back_to_settings$", callback=settings.send_menage_apps_menu)
        ],
        allow_reentry=True,  # per consentire di rimuovere un'altra app o riselezionare l'app
    )

    conv_handler2 = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pattern="settings", callback=settings.change_settings),
            CallbackQueryHandler(pattern="^default_setting_finished.+$", callback=send_menu)
        ],
        states={
            ConversationState.CHANGE_SETTINGS: [
                CallbackQueryHandler(pattern="menage_apps", callback=settings.menage_apps),
                conv_handler1,
                CallbackQueryHandler(pattern="^back_to_main_menu$", callback=send_menu)
            ],
            ConversationState.MANAGE_APPS: [
                add_app_conv_handler,
                edit_app_conv_handler,
                delete_app_conv_handler,
                CallbackQueryHandler(pattern="list_apps", callback=settings.list_apps),
                CallbackQueryHandler(pattern="unsuspend_app", callback=settings.suspend_app),
                CallbackQueryHandler(pattern="^back_to_main_settings$", callback=settings.menage_apps),
                CallbackQueryHandler(pattern="settings", callback=settings.change_settings),
                CallbackQueryHandler(pattern="back_to_settings_settled", callback=settings.send_menage_apps_menu)
            ],
            ConversationState.LIST_APPS: [
                CallbackQueryHandler(pattern="back_from_list", callback=settings.menage_apps)
            ],
            ConversationState.UNSUSPEND_APP: [
                CallbackQueryHandler(pattern="^unsuspend_app.+$", callback=settings.suspend_app),
                CallbackQueryHandler(pattern="^back_to_main_settings.+$", callback=settings.menage_apps)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(pattern="^back_to_settings$", callback=settings.menage_apps),
            CallbackQueryHandler(pattern="^back_to_settings_no_apps$", callback=settings.send_menage_apps_menu),
            CallbackQueryHandler(pattern="^back_to_settings_settled$", callback=settings.send_menage_apps_menu)
        ],
        allow_reentry=True
    )

    # app.add_handler(TypeHandler(Update, callback=catch_update), group=-1)

    app.add_handler(conv_handler1)
    app.add_handler(conv_handler2)

    app.add_handler(CallbackQueryHandler(pattern="^suspend_app.+$", callback=settings.suspend_app))
    app.add_handler(CallbackQueryHandler(pattern="^delete_message.+$",
                                         callback=settings.delete_extemporary_message))
    app.add_handler(CallbackQueryHandler(pattern="^edit_from_job.+$", callback=settings.see_app_settings))
    app.add_handler(set_app_conv_handler)

    app.run_polling()


if __name__ == '__main__':
    load_dotenv()
    main()
