from telegram.constants import ChatAction
from telegram.ext import CallbackContext, ConversationHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from datetime import timedelta
from bs4 import BeautifulSoup

import telegram
import logging
import requests
from logging import handlers
import job_queue

settings_logger = logging.getLogger("settings_logger")
settings_logger.setLevel(logging.INFO)
file_handler = handlers.RotatingFileHandler(filename="../misc/logs/settings.log",
                                            maxBytes=1024, backupCount=1)
settings_logger.addHandler(file_handler)

CHANGE_SETTINGS, MENAGE_APPS, LIST_LAST_CHECKS, MENAGE_APPS_OPTIONS, LIST_APPS, ADD_APP = range(5)

LINK_OR_NAME, CONFIRM_APP_NAME, FIX_WEBPAGE_ANALYSIS = range(3)


async def set_defaults(update: Update, context: CallbackContext):
    if update.callback_query is not None and (update.callback_query.data.startswith("set_defaults") or
                                              update.callback_query.data.startswith("interval_incorrect")):
        if len(li := update.callback_query.data.split(" ")) > 1:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id,
                                                 message_id=int(li[1]))
            except telegram.error.BadRequest:
                pass

        context.bot_data["settings"]["tutorial"] = True

        message = await context.bot.send_message(chat_id=update.effective_chat.id,
                                                 text="🔧 <b>Setting Default Values</b>\n\n"
                                                      "➡ <u>Default Checking Interval</u> – Se non specificherai un "
                                                      "intervallo di controllo, verrà settato quello che stai "
                                                      "impostando adesso.\n\n"
                                                      "❔ <b>Format</b>\nFornisci una stringa nel formato ↙\n\n "
                                                      "<code>?m?d?h?min?s</code>\n\nsostituendo i <code>?</code> con i "
                                                      "valori corrispondenti di:\n\n"
                                                      "\t1️⃣ <code>m</code> – Mesi\n"
                                                      "\t2️⃣ <code>d</code> – Giorni\n"
                                                      "\t3️⃣ <code>h</code> – Ore\n"
                                                      "\t4️⃣ <code>min</code> – Minuti\n"
                                                      "\t5️⃣ <code>s</code> – Secondi\n\n"
                                                      "Inserisci tutti i valori corrispondenti anche se nulli.\n\n "
                                                      "<b>Esempio</b> 🔎 – <code>0m2d0h15min0s</code>\n\n"
                                                      "🔹Non è un valore definitivo: lo puoi cambiare quando vorrai.",
                                                 parse_mode="HTML")
        context.chat_data["messages_to_delete"] = message.id
        return 2

    if update.callback_query is None and update.message is not None:
        try:
            months = int(update.message.text.split('m')[0])
            days = int(update.message.text.split('d')[0].split('m')[1])
            hours = int(update.message.text.split('h')[0].split('d')[1])
            minutes = int(update.message.text.split('min')[0].split('h')[1])
            seconds = int(update.message.text.split('s')[0].split('min')[1])

            context.job_queue.run_once(callback=job_queue.scheduled_delete_message,
                                       data={
                                           "chat_id": update.effective_chat.id,
                                           "message_id": update.message.id,
                                       },
                                       when=2.5)

            context.job_queue.run_once(callback=job_queue.scheduled_delete_message,
                                       data={
                                           "chat_id": update.effective_chat.id,
                                           "message_id": context.chat_data["messages_to_delete"],
                                       },
                                       when=2)
            del context.chat_data["messages_to_delete"]

        except ValueError:
            text = ("❌ <b>Usa il formato indicato</b>, non aggiungere, togliere o cambiare lettere."
                    "\n\n🔎 <code>#m#d#h#min#s</code>")
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=text, parse_mode="HTML")
            return 2
        else:
            context.bot_data["settings"]["default_check_interval"]["timedelta"] = timedelta(days=days + months * 30,
                                                                                            seconds=seconds,
                                                                                            minutes=minutes,
                                                                                            hours=hours)
            context.bot_data["settings"]["default_check_interval"]["input"] = {
                "days": days,
                "months": months,
                "seconds": seconds,
                "minutes": minutes,
                "hours": hours
            }
            text = (f"❓ Conferma se l'intervallo indicato è corretto.\n\n"
                    f"▪️ <code>{months}</code> mesi\n"
                    f"▪️ <code>{days}</code> giorni\n"
                    f"▪️ <code>{hours}</code> ore\n"
                    f"▪️ <code>{minutes}</code> minuti\n"
                    f"▪️ <code>{seconds}</code> secondi")
            message = await context.bot.send_message(chat_id=update.effective_chat.id,
                                                     text=text,
                                                     parse_mode="HTML")
            keyboard = [
                [
                    InlineKeyboardButton(text="✅ È corretto.", callback_data=f"interval_correct {message.id}"),
                    InlineKeyboardButton(text="❌ Non è corretto.", callback_data=f"interval_incorrect {message.id}")
                ]
            ]
            await context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                                        message_id=message.id,
                                                        reply_markup=InlineKeyboardMarkup(keyboard))
            return 2

    if update.callback_query.data.startswith("interval_correct"):
        if len(li := update.callback_query.data.split(" ")) > 1:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id,
                                                 message_id=int(li[1]))
            except telegram.error.BadRequest:
                pass
        text = ("🔧 <b>Setting Default Values</b>\n\n"
                "➡ <u>Default Checking Interval</u> – Scegli se, di default, ti verrà mandato un messaggio <b>solo "
                "quando viene trovato un aggiornamento</b> (<code>False</code>) o <b>ad ogni controllo</b>"
                " (<code>True</code>)."
                "\n\n🔹Potrai cambiare questa impostazione in seguito.")

        message = await context.bot.send_message(chat_id=update.effective_chat.id,
                                                 text=text,
                                                 parse_mode="HTML")
        keyboard = [
            [
                InlineKeyboardButton(text="✅ True", callback_data=f"default_send_on_check_true {message.id}"),
                InlineKeyboardButton(text="❌ False", callback_data=f"default_send_on_check_false {message.id}")
            ]
        ]
        await context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                                    message_id=message.id,
                                                    reply_markup=InlineKeyboardMarkup(keyboard))
        return 3

    if update.callback_query.data.startswith("default_send_on_check"):
        if len(li := update.callback_query.data.split(" ")) > 1:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id,
                                                 message_id=int(li[1]))
            except telegram.error.BadRequest:
                pass
        if update.callback_query.data.startswith("default_send_on_check_true"):
            context.bot_data["settings"]["default_send_on_check"] = True
        else:
            context.bot_data["settings"]["default_send_on_check"] = False

        interval_input = context.bot_data["settings"]["default_check_interval"]["input"]

        keyboard = [
            [InlineKeyboardButton(text="⏭ Procedi", callback_data="default_setting_finished {}")]
        ]
        await context.bot.send_chat_action(chat_id=update.effective_chat.id,
                                           action=ChatAction.TYPING)
        context.job_queue.run_once(callback=job_queue.scheduled_send_message,
                                   data={
                                       "chat_id": update.effective_chat.id,
                                       "text": f"☑️ <b>Setting Completed</b>\n\n"
                                               f"🔸 <u>Default Interval</u> – "
                                               f"<code>{interval_input["months"]}m"
                                               f"{interval_input["days"]}d"
                                               f"{interval_input["hours"]}h"
                                               f"{interval_input["minutes"]}min"
                                               f"{interval_input["seconds"]}s</code>\n"
                                               f"🔸 <u>Default Send On Check</u> – "
                                               f"<code>{str(context.bot_data["settings"]["default_send_on_check"])}"
                                               f"</code>\n\n"
                                               f"🔹Premi il tasto sotto per procedere.",
                                       "keyboard": keyboard,
                                       "close_button": [1, 1]
                                   },
                                   when=1)
        return ConversationHandler.END


async def change_settings(update: Update, context: CallbackContext):
    text = ("⚙ <b>Settings Panel</b>\n\n🔹Da qui puoi cambiare le impostazioni di default e gestire le applicazioni "
            "monitorate.\n\n🔸 Scegli un'opzione.")

    keyboard = [
        [
            InlineKeyboardButton(text="🗂 Gestisci App", callback_data="menage_apps"),
            InlineKeyboardButton(text="🔧 Imp. Default", callback_data="edit_default_settings")
        ],
        [InlineKeyboardButton(text="🔙 Menu Principale", callback_data="start_menu")]
    ]

    await parse_conversation_message(data={
        "chat_id": update.effective_chat.id,
        "message_id": update.effective_message.message_id,
        "text": text,
        "reply_markup": InlineKeyboardMarkup(keyboard),
        "parse_mode": "HTML"
    }, context=context)

    return CHANGE_SETTINGS


async def menage_apps(update: Update, context: CallbackContext):
    if update.callback_query:
        if update.callback_query.data == "menage_apps" or update.callback_query.data.startswith(
                "back_to_main_settings"):
            text = ("🗂 <b>Gestione Applicazioni</b>\n\n"
                    "🔹Da questo menù, puoi visualizzare e gestire le applicazioni.")

            keyboard = [
                [
                    InlineKeyboardButton(text="📄 Lista App", callback_data="list_apps"),
                    InlineKeyboardButton(text="➕ Aggiungi", callback_data="add_app"),
                    InlineKeyboardButton(text="➖ Rimuovi", callback_data="remove_app")
                ],
                [InlineKeyboardButton(text="🔙 Torna Indietro",
                                      callback_data=f"back_to_main_menu {update.effective_message.id}")]
            ]

            await parse_conversation_message(data={
                "chat_id": update.effective_chat.id,
                "message_id": update.effective_message.message_id,
                "text": text,
                "reply_markup": InlineKeyboardMarkup(keyboard),
                "parse_mode": "HTML"
            }, context=context)

            return MENAGE_APPS

        if update.callback_query.data == "list_apps" or update.callback_query.data == "go_back_to_list_apps":
            if len(context.bot_data["apps"]) == 0:
                keyboard = [
                    [
                        InlineKeyboardButton(text="➕ Aggiungi", callback_data="add_app"),
                        InlineKeyboardButton(text="🔙 Torna Indietro",
                                             callback_data=f"back_to_main_settings {update.effective_message.id}")
                    ]
                ]
                text = ("🅾️ <code>No Apps Yet</code>\n\n"
                        "🔸Usa la tastiera per aggiungerne")

                await parse_conversation_message(data={
                    "chat_id": update.effective_chat.id,
                    "message_id": update.effective_message.message_id,
                    "text": text,
                    "reply_markup": InlineKeyboardMarkup(keyboard),
                    "parse_mode": "HTML"
                }, context=context)

            else:
                keyboard = [
                    [
                        InlineKeyboardButton(text="➕ Aggiungi", callback_data="add_app"),
                        InlineKeyboardButton(text="➖ Rimuovi", callback_data="remove_app"),
                        InlineKeyboardButton(text="🖋 Modifica", callback_data="edit_app")
                    ],
                    [InlineKeyboardButton(text="🔎 Dettagli App", callback_data="info_app")],
                    [InlineKeyboardButton(text="🔙 Torna Indietro",
                                          callback_data=f"back_to_main_settings {update.effective_message.id}")]
                ]

                text = "👁‍🗨 <b>Watched Apps</b>\n\n"
                for count, app in enumerate(context.bot_data["apps"], start=1):
                    text += (f"  {count}. {context.bot_data['apps'][str(count)]["app_name"]}\n"
                             f"    <code>Interval</code> {context.bot_data['apps'][str(count)]["check_interval"]}\n"
                             f"    <code>Send On Check</code> {context.bot_data['apps'][str(count)]["send_on_check"]}\n"
                             )

                text += "\n🆘 Per i dettagli su un'applicazione, scegli 🖋 Modifica\n\n🔸Scegli un'opzione"

                await parse_conversation_message(data={
                    "chat_id": update.effective_chat.id,
                    "message_id": update.effective_message.message_id,
                    "text": text,
                    "reply_markup": InlineKeyboardMarkup(keyboard),
                    "parse_mode": "HTML"
                }, context=context)

            return LIST_APPS

        if update.callback_query.data == "add_app" or update.callback_query.data == "go_back_to_add_app":
            pass

        if update.callback_query.data == "remove_app" or update.callback_query.data == "go_back_to_remove_app":
            pass

        if update.callback_query.data == "edit_app" or update.callback_query.data == "go_back_to_edit_app":
            pass

        if update.callback_query.data == "info_app" or update.callback_query.data == "go_back_to_info_app":
            pass

    else:
        if "previous_step" in context.chat_data:
            if context.chat_data["previous_step"] == "add_app":
                pass


async def edit_default_settings(update: Update, context: CallbackContext):
    pass


async def close_menu(update: Update, context: CallbackContext):
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id,
                                         message_id=int(update.callback_query.data.split(" ")[1]))
    except telegram.error.BadRequest:
        pass
    finally:
        return ConversationHandler.END


async def add_app(update: Update, context: CallbackContext):

    if update.callback_query and update.callback_query.data == "add_app":
        text = "➕ <b>Aggiungi App</b>\n\n"

        if len(context.bot_data["apps"]) != 0:
            text += "🗃 <u>Elenco</u>\n\n"
            for count, app in enumerate(context.bot_data["apps"], start=1):
                text += f"  {count}. {context.bot_data['apps'][str(count)]["app_name"]}\n\n"

        text += "🔸Puoi fornire o il nome dell'app o il link allo store Google Play"

        keyboard = [
            [InlineKeyboardButton(text="🔙 Torna Indietro",
                                  callback_data=f"back_to_main_settings {update.effective_message.id}")]
        ]

        context.chat_data["message_to_delete"] = update.effective_message.id

        await parse_conversation_message(data={
            "chat_id": update.effective_chat.id,
            "message_id": update.effective_message.message_id,
            "text": text,
            "reply_markup": InlineKeyboardMarkup(keyboard),
            "parse_mode": "HTML"
        }, context=context)

        return LINK_OR_NAME

    message = update.effective_message if update.effective_message else None

    if message and len(message.parse_entity(MessageEntity.url)) == 1:
        # è stato specificato un link
        res = requests.get(message.text)
        if res.status_code != 200:
            settings_logger.warning(f"Not able to gather link {message.text}")
            raise telegram.error.NetworkError("Not able to get link.")

        if name := BeautifulSoup(res.text, "html.parser").find('h1', itemprop='name') is None:
            keyboard = [
                [InlineKeyboardButton(text="🔙 Torna Indietro",
                                      callback_data=f"back_to_main_settings {message.id}")]
            ]
            text = ("⚠️ Non sono riuscito a rilevare l'applicazione.\n\n"
                    "🆘 Se pensi che io abbia fatto un errore, <u>potrebbe essere che la struttura della pagina web "
                    "del link sia cambiata</u>. In tal caso, <b>prova a scrivere il nome dell'applicazione</b> "
                    "che dovrei rilevare (non dimenticare spazi, simboli o lettere maiuscole).\n\n"
                    "🔸Rimanda il link o fornisci il nome esatto dell'applicazione")

            context.chat_data["name_for_fix"] = True

            await parse_conversation_message(context=context, data={
                "chat_id": update.effective_chat.id,
                "message_id": message.message_id,
                "text": text,
                "reply_markup": InlineKeyboardMarkup(keyboard)
            })

            return FIX_WEBPAGE_ANALYSIS

        else:
            keyboard = [
                [InlineKeyboardButton(text="✅ Si", callback_data="app_name_from_link_correct")],
                [InlineKeyboardButton(text="❌ No", callback_data="app_name_from_link_not_correct")]
            ]

            text = f"❔ Il nome dell'applicazione è <code>{name}</code>?"

            await parse_conversation_message(context=context, data={
                "chat_id": update.effective_chat.id,
                "message_id": message.message_id,
                "text": text,
                "reply_markup": InlineKeyboardMarkup(keyboard)
            })

            return CONFIRM_APP_NAME

    else:
        if "name_for_fix" in context.chat_data and context.chat_data["name_for_fix"] is True:
            # il nome è stato mandato per correggere l'analisi della pagina web
            pass

        else:
            # il nome è stato mandato al posto del link: bisogna cercarla
            pass

    if "message_to_delete" in context.chat_data:
        context.job_queue.run_once(callback=job_queue.scheduled_delete_message,
                                   data={
                                       "message_id": context.chat_data["message_to_delete"],
                                       "chat_id": update.effective_chat.id
                                   },
                                   when=2)
        del context.chat_data["message_to_delete"]

    if message:
        context.job_queue.run_once(callback=job_queue.scheduled_delete_message,
                                   data={
                                       "message_id": message.message_id,
                                       "chat_id": update.effective_chat.id
                                   },
                                   when=2.5)

    return ADD_APP


async def parse_conversation_message(context: CallbackContext, data: dict):
    check_dict_keys(data, ["chat_id", "message_id", "text", "reply_markup"])

    chat_id, message_id, text, reply_markup = data["chat_id"], data["message_id"], data["text"], data["reply_markup"]

    try:
        await context.bot.edit_message_text(chat_id=chat_id,
                                            message_id=message_id,
                                            text=text,
                                            reply_markup=reply_markup,
                                            parse_mode="HTML")
    except telegram.error.BadRequest as e:
        settings_logger.warning(f"Not able to edit message: {e}\nA new one will be sent.")
        await context.bot.send_message(chat_id=chat_id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode="HTML")


def check_dict_keys(d: dict, keys: list):
    mancanti = [key for key in keys if key not in d]
    if len(mancanti) != 0:
        raise Exception(f"Missing key(s): {mancanti} in dictionary {d}")
