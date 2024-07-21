import logging
import os
from datetime import timedelta, datetime
from logging import handlers

import pytz

import requests
import telegram
from time import sleep
from google_play_scraper import app
from google_play_scraper.exceptions import NotFoundError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, ConversationHandler, ContextTypes

import job_queue
from decorators import send_action

settings_logger = logging.getLogger("settings_logger")
settings_logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = handlers.RotatingFileHandler(filename="../misc/logs/settings.log",
                                            maxBytes=1024, backupCount=1)
file_handler.setFormatter(formatter)
settings_logger.addHandler(file_handler)

bot_logger = logging.getLogger("bot_logger")

CHANGE_SETTINGS, MENAGE_APPS, LIST_LAST_CHECKS, MENAGE_APPS_OPTIONS, LIST_APPS, ADD_APP = range(6)

SEND_LINK, CONFIRM_APP_NAME = range(2)

SET_INTERVAL, CONFIRM_INTERVAL, SEND_ON_CHECK, SET_UP_ENDED = range(4)

EDIT_SELECT_APP, EDIT_CONFIRM_APP = range(2)

DELETE_APP_SELECT, DELETE_APP_CONFIRM = range(2)


@send_action(ChatAction.TYPING)
async def set_defaults(update: Update, context: CallbackContext):
    if update.callback_query and update.callback_query.data == "edit_default_settings":
        await delete_message(context=context, chat_id=update.effective_chat.id,
                             message_id=update.effective_message.message_id)
        inp = context.bot_data["settings"]["default_check_interval"]["input"]
        text = (f"🔧 <b>Impostazioni di Default</b>\n\n"
                f"  🔹 <u>Default Interval</u> "
                f"<code>{inp["months"]}m{inp["days"]}d{inp["hours"]}h{inp["minutes"]}min{inp["seconds"]}s</code>\n"
                f"  🔹 <u>Default Send On Check</u> "
                f"<code>{context.bot_data["settings"]["default_send_on_check"]}</code>\n\n"
                f"🔸 Scegli un'opzione")

        sleep(1)

        message_id = await parse_conversation_message(context=context, data={
            "chat_id": update.effective_chat.id,
            "text": text,
            "message_id": update.effective_message.message_id,
            "reply_markup": False
        })

        keyboard = [
            [
                InlineKeyboardButton(text="✏ Modifica", callback_data=f"confirm_edit_default_settings {message_id}"),
                InlineKeyboardButton(text="🔙 Torna Indietro", callback_data="cancel_edit_settings")
            ]
        ]

        await context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                                    message_id=message_id,
                                                    reply_markup=InlineKeyboardMarkup(keyboard))

        return 0

    if update.callback_query and (update.callback_query.data.startswith("set_defaults") or
                                  update.callback_query.data.startswith("interval_incorrect") or
                                  update.callback_query.data.startswith("confirm_edit_default_settings")):

        bot_logger.info("Starting to set default settings.")

        if "message_to_delete" in context.chat_data:
            await delete_message(context=context, chat_id=update.effective_chat.id,
                                 message_id=context.chat_data["message_to_delete"])
            del context.chat_data["message_to_delete"]

        if len(li := update.callback_query.data.split(" ")) > 1:
            await delete_message(context=context, message_id=int(li[1]), chat_id=update.effective_chat.id)

        context.bot_data["settings"]["tutorial"] = True

        sleep(1)

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

    if not update.callback_query and update.message:
        try:
            # noinspection DuplicatedCode
            months = int(update.message.text.split('m')[0])
            days = int(update.message.text.split('d')[0].split('m')[1])
            hours = int(update.message.text.split('h')[0].split('d')[1])
            minutes = int(update.message.text.split('min')[0].split('h')[1])
            seconds = int(update.message.text.split('s')[0].split('min')[1])

            context.job_queue.run_once(callback=job_queue.scheduled_delete_message,
                                       data={
                                           "chat_id": update.effective_chat.id,
                                           "message_id": context.chat_data["messages_to_delete"],
                                       },
                                       when=2)

            context.job_queue.run_once(callback=job_queue.scheduled_delete_message,
                                       data={
                                           "chat_id": update.effective_chat.id,
                                           "message_id": update.message.id,
                                       },
                                       when=2.5)

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

            # noinspection DuplicatedCode
            text = (f"❓ Conferma se l'intervallo indicato è corretto.\n\n"
                    f"▫️️ <code>{months}</code> mesi\n"
                    f"▫️ <code>{days}</code> giorni\n"
                    f"▫️ <code>{hours}</code> ore\n"
                    f"▫️ <code>{minutes}</code> minuti\n"
                    f"▫️ <code>{seconds}</code> secondi")
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            sleep(1)
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

    if update.callback_query and update.callback_query.data.startswith("interval_correct"):
        i = context.bot_data["settings"]["default_check_interval"]["input"]
        bot_logger.info(f"Default Interval -> Setting Completed: "
                        f"{i["months"]}m{i["days"]}d{i["months"]}h{i["months"]}min{i["months"]}s")

        if len(li := update.callback_query.data.split(" ")) > 1:
            await delete_message(context=context, chat_id=update.effective_chat.id,
                                 message_id=int(li[1]))

        text = ("🔧 <b>Setting Default Values</b>\n\n"
                "➡ <u>Default Send On Check</u> – Scegli se, di default, ti verrà mandato un messaggio <b>solo "
                "quando viene trovato un aggiornamento</b> (<code>False</code>) o <b>ad ogni controllo</b>"
                " (<code>True</code>)."
                "\n\n🔹Potrai cambiare questa impostazione in seguito.")

        sleep(1)

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

    if update.callback_query and update.callback_query.data.startswith("default_send_on_check"):
        i = context.bot_data["settings"]["default_check_interval"]["input"]
        if len(li := update.callback_query.data.split(" ")) > 1:
            await delete_message(context=context, chat_id=update.effective_chat.id,
                                 message_id=int(li[1]))

        if update.callback_query.data.startswith("default_send_on_check_true"):
            context.bot_data["settings"]["default_send_on_check"] = True
        else:
            context.bot_data["settings"]["default_send_on_check"] = False

        bot_logger.info(f"Default Send On Check -> Setting Completed: "
                        f"{context.bot_data["settings"]["default_send_on_check"]}")

        bot_logger.info(f"Default Setting Completed.")

        text = (f"☑️ <b>Setting Completed</b>\n\n"
                f"🔸 <u>Default Interval</u> – "
                f"<code>{i["months"]}m"
                f"{i["days"]}d"
                f"{i["hours"]}h"
                f"{i["minutes"]}min"
                f"{i["seconds"]}s</code>\n"
                f"🔸 <u>Default Send On Check</u> – "
                f"<code>{str(context.bot_data["settings"]["default_send_on_check"])}"
                f"</code>\n\n"
                f"🔹Premi il tasto sotto per procedere.")

        sleep(1)
        message = await context.bot.send_message(chat_id=update.effective_chat.id,
                                                 text=text,
                                                 parse_mode="HTML")
        keyboard = [
            [InlineKeyboardButton(text="⏭ Procedi", callback_data=f"default_setting_finished {message.id}")]
        ]

        await context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                                    message_id=message.id,
                                                    reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END


async def change_settings(update: Update, context: CallbackContext):
    text = ("⚙ <b>Settings Panel</b>\n\n🔹Da qui puoi cambiare le impostazioni di default e gestire le applicazioni "
            "monitorate.\n\n🔸 Scegli un'opzione.")

    keyboard = [
        [
            InlineKeyboardButton(text="🗂 Gestisci App", callback_data="menage_apps"),
            InlineKeyboardButton(text="🔧 Imp. Default", callback_data="edit_default_settings")
        ],
        [InlineKeyboardButton(text="🔙 Menu Principale", callback_data="back_to_main_menu")]
    ]

    await parse_conversation_message(context=context,
                                     data={
                                         "chat_id": update.effective_chat.id,
                                         "message_id": update.effective_message.message_id,
                                         "text": text,
                                         "reply_markup": InlineKeyboardMarkup(keyboard)}
                                     )

    return CHANGE_SETTINGS if update.callback_query.data != "cancel_edit_settings" else ConversationHandler.END


async def menage_apps(update: Update, context: CallbackContext):
    if update.callback_query:
        if update.callback_query.data == "menage_apps" or update.callback_query.data.startswith(
                "back_to_main_settings"):

            if "format_message" in context.chat_data:
                await delete_message(context=context,
                                     message_id=context.chat_data["format_message"],
                                     chat_id=update.effective_chat.id)
                del context.chat_data["format_message"]

            if "message_to_delete" in context.chat_data:
                await schedule_messages_to_delete(context=context,
                                                  messages={
                                                      int(context.chat_data["message_to_delete"]): {
                                                          "chat_id": update.effective_chat.id,
                                                          "time": 2
                                                      }
                                                  })

                del context.chat_data["message_to_delete"]

            text = ("🗂 <b>Gestione Applicazioni</b>\n\n"
                    "🔹Da questo menù, puoi visualizzare e gestire le applicazioni.")

            keyboard = [
                [
                    InlineKeyboardButton(text="✏️ Modifica", callback_data="edit_app"),
                    InlineKeyboardButton(text="➕ Aggiungi", callback_data="add_app"),
                    InlineKeyboardButton(text="➖ Rimuovi", callback_data="delete_app")
                ],
                [
                    InlineKeyboardButton(text="⏸ Sospendi App", callback_data="suspend_app"),
                    InlineKeyboardButton(text="📄 Lista App", callback_data="list_apps")
                ],
                [
                    InlineKeyboardButton(text="🔙 Torna Indietro",
                                         callback_data=f"settings {update.effective_message.id}")
                ]
            ]

            await parse_conversation_message(context=context,
                                             data={
                                                 "chat_id": update.effective_chat.id,
                                                 "message_id": update.effective_message.message_id,
                                                 "text": text,
                                                 "reply_markup": InlineKeyboardMarkup(keyboard)}
                                             )

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

                await parse_conversation_message(context=context,
                                                 data={
                                                     "chat_id": update.effective_chat.id,
                                                     "message_id": update.effective_message.message_id,
                                                     "text": text,
                                                     "reply_markup": InlineKeyboardMarkup(keyboard)})

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
                for a in context.bot_data["apps"]:
                    text += (f"  {a}. {context.bot_data['apps'][str(a)]["app_name"]}\n"
                             f"    <code>Interval</code> {context.bot_data['apps'][str(a)]["check_interval"]}\n"
                             f"    <code>Send On Check</code> {context.bot_data['apps'][str(a)]["send_on_check"]}\n"
                             )

                text += "\n🆘 Per i dettagli su un'applicazione, scegli 🖋 Modifica\n\n🔸Scegli un'opzione"

                await parse_conversation_message(context=context,
                                                 data={
                                                     "chat_id": update.effective_chat.id,
                                                     "message_id": update.effective_message.message_id,
                                                     "text": text,
                                                     "reply_markup": InlineKeyboardMarkup(keyboard)}
                                                 )

            return LIST_APPS

        if update.callback_query.data == "remove_app" or update.callback_query.data == "go_back_to_remove_app":
            pass

        if update.callback_query.data == "edit_app" or update.callback_query.data == "go_back_to_edit_app":
            pass

        if update.callback_query.data == "info_app" or update.callback_query.data == "go_back_to_info_app":
            pass


async def close_menu(update: Update, context: CallbackContext):
    await delete_message(context=context, chat_id=update.effective_chat.id,
                         message_id=int(update.callback_query.data.split(" ")[1]))

    return ConversationHandler.END


@send_action(action=ChatAction.TYPING)
async def list_apps(update: Update, context: CallbackContext):
    await delete_message(context=context, chat_id=update.effective_chat.id, message_id=update.effective_message.id)

    text = "🗃 <b>App List</b>\n\n"

    if len(context.bot_data["apps"]) == 0:
        text += ("ℹ Nessuna app aggiunta.\n\n"
                 "🔸 Scegli un'opzione")

    else:
        for a in context.bot_data["apps"]:
            ap = context.bot_data["apps"][a]
            text += (f"  {a}. {ap["app_name"]}\n"
                     f"    App ID: <code>{ap["app_id"]}</code>\n"
                     f"    App Link: <a href=\"{ap["app_link"]}\">link 🔗</a>\n"
                     f"    Current Version: <code>{ap["current_version"]}</code>\n"
                     f"    Last Update: <code>{ap["last_update"]}</code>\n\n"
                     f"    Check Interval: <code>"
                     f"{ap["check_interval"]["input"]["months"]}m"
                     f"{ap["check_interval"]["input"]["days"]}d"
                     f"{ap["check_interval"]["input"]["hours"]}h"
                     f"{ap["check_interval"]["input"]["minutes"]}min"
                     f"{ap["check_interval"]["input"]["seconds"]}s</code>\n"
                     f"    Send On Check: <code>{ap["send_on_check"]}</code>\n\n")
            
            text += (f"    Last Check: <code>None</code>" 
                     if ap["last_check"] is None 
                     else f"    Last Check: <code>{ap["last_check"].strptime('%d %B %Y – %H:%M:%S')}</code>\n")
            
            text += (f"    Next Check: <code>{ap["next_check"].strptime('%d %B %Y – %H:%M:%S')}</code>\n\n"
                     f"    <b>Suspended</b>: <code>{ap["suspended"]}</code>\n\n")

    sleep(1)
    await parse_conversation_message(context=context, data={
        "chat_id": update.effective_chat.id,
        "text": text,
        "message_id": -1,
        "reply_markup": None
    })

    return LIST_APPS


async def add_app(update: Update, context: CallbackContext):
    if update.callback_query and update.callback_query.data == "add_app":
        text = "➕ <b>Add App</b>\n\n"

        if len(context.bot_data["apps"]) != 0:
            text += "🗃 <u>Elenco</u>\n\n"
            for ap in context.bot_data["apps"]:
                text += f"  {ap}. {context.bot_data['apps'][str(ap)]["app_name"]}\n"

        text += "\n🔸 Manda il link all'applicazione su Google Play"

        context.chat_data["send_link_message"] = update.effective_message.id

        await parse_conversation_message(data={
            "chat_id": update.effective_chat.id,
            "message_id": update.effective_message.message_id,
            "text": text,
            "reply_markup": None
        }, context=context)

        return SEND_LINK

    not_cquery_message = update.effective_message if update.effective_message and not update.callback_query else None

    if not_cquery_message:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id,
                                           action=ChatAction.TYPING)
        if len(entities := not_cquery_message.entities) == 1 and entities[0].type == MessageEntity.URL:
            if "message_to_delete" in context.chat_data:
                await delete_message(context=context, chat_id=update.effective_chat.id,
                                     message_id=context.chat_data["message_to_delete"])
                del context.chat_data["message_to_delete"]

            link = update.message.text[entities[0].offset:]
            res = requests.get(link)

            if res.status_code != 200:
                settings_logger.warning(f"Not able to gather link {link}: {res.reason}")
                text = (f"❌ A causa di un problema di rete, non riuscito a reperire il link che hai mandato.\n\n"
                        f"🔍 <i>Reason</i>\n{res.reason}\n\n"
                        f"🆘 Se il problema persiste, contatta @AleLntr\n\n"
                        f"🔸 Puoi riprovare a mandare lo stesso link o cambiarlo")

                await parse_conversation_message(context=context,
                                                 data={
                                                     "chat_id": update.effective_chat.id,
                                                     "message_id": not_cquery_message.id,
                                                     "text": text,
                                                     "reply_markup": None
                                                 })

                return SEND_LINK

            app_details = await get_app_details_with_link(link=link)

            if isinstance(app_details, NotFoundError) or isinstance(app_details, IndexError):
                if isinstance(app_details, NotFoundError):
                    text = ("⚠️ Ho avuto problemi a reperire l'applicazione.\n\n"
                            "Potrebbe essere un problema di API o l'applicazione potrebbe essere stata rimossa.\n\n"
                            "🔸 Contatta @AleLntr per risolvere il problema, o manda un altro link")
                else:
                    text = "❌ Sembra che il link non sia corretto (manca l'ID del pacchetto)"

                message_id = await parse_conversation_message(context=context,
                                                              data={
                                                                  "chat_id": update.effective_chat.id,
                                                                  "message_id": -1,
                                                                  "text": text,
                                                                  "reply_markup": None
                                                              })

                context.chat_data["message_to_delete"] = message_id

                await schedule_messages_to_delete(context=context,
                                                  messages={
                                                      update.effective_message.id: {
                                                          "chat_id": update.effective_chat.id,
                                                          "time": 2
                                                      }
                                                  })

                return SEND_LINK

            else:
                if "send_link_message" in context.chat_data:
                    await delete_message(context=context,
                                         chat_id=update.effective_chat.id,
                                         message_id=context.chat_data["send_link_message"])
                    del context.chat_data["send_link_message"]

                name = app_details.get('title')
                current_version = app_details.get('version')
                last_update = datetime.strptime(app_details.get('lastUpdatedOn'), '%b %d, %Y')
                app_id = app_details.get('appId')

                if name is None or current_version is None or last_update is None or app_id is None:
                    settings_logger.warning("Gathered App Detail is None. Check bot_data for reference.")

                context.chat_data["setting_app"] = {
                    "app_name": name,
                    "app_link": link,
                    "current_version": current_version,
                    "last_update": last_update,
                    "app_id": app_id
                }

                keyboard = [
                    [
                        InlineKeyboardButton(text="✅ Si", callback_data="app_name_from_link_correct"),
                        InlineKeyboardButton(text="❌ No", callback_data="app_name_from_link_not_correct")]
                ] if name else None

                text = f"❔ Il nome dell'applicazione è <b>{name}</b>?" \
                    if name else (f"⚠️ Il nome dell'applicazione è <code>None</code>. È possibile che ci sia "
                                  f"un problema di API o di struttura della pagina web.\n\n"
                                  f"🔸 Contatta @AleLntr per risolvere il problema, oppure <u>invia un altro link</u>")

                message_id = await parse_conversation_message(context=context,
                                                              data={
                                                                  "chat_id": update.effective_chat.id,
                                                                  "message_id": -1,
                                                                  "text": text,
                                                                  "reply_markup": InlineKeyboardMarkup(
                                                                      keyboard) if keyboard else None
                                                              })

                context.chat_data["message_to_delete"] = message_id

                await schedule_messages_to_delete(context=context,
                                                  messages={
                                                      update.effective_message.id: {
                                                          "chat_id": update.effective_chat.id,
                                                          "time": 5
                                                      }
                                                  })

                return CONFIRM_APP_NAME if name else SEND_LINK

        else:
            if "send_link_message" in context.chat_data:
                await delete_message(context=context, chat_id=update.effective_chat.id,
                                     message_id=context.chat_data["send_link_message"])
                del context.chat_data["send_link_message"]

            keyboard = [
                [
                    InlineKeyboardButton(text="🔙 Torna Indietro",
                                         callback_data=f"back_to_main_settings {not_cquery_message.id}"),
                    InlineKeyboardButton(text="🆘 Contatta @AleLntr", url='https://t.me/AleLntr')
                ]
            ]

            text = "❌ Non hai mandato un link valido o hai mandato più di un link nello stesso messaggio."

            message_id = await parse_conversation_message(context=context, data={
                "chat_id": update.effective_chat.id,
                "message_id": -1,
                "text": text,
                "reply_markup": InlineKeyboardMarkup(keyboard)
            })

            await schedule_messages_to_delete(context=context,
                                              messages={
                                                  int(not_cquery_message.id): {
                                                      "time": 2,
                                                      "chat_id": update.effective_chat.id,
                                                  }
                                              })

            context.chat_data["send_link_message"] = message_id

            return SEND_LINK

    if update.callback_query and update.callback_query.data == "app_name_from_link_not_correct":
        if "message_to_delete" in context.chat_data:
            del context.chat_data["message_to_delete"]

        if "send_link_message" in context.chat_data:
            await delete_message(context=context,
                                 chat_id=update.effective_chat.id,
                                 message_id=context.chat_data["send_link_message"])
            del context.chat_data["send_link_message"]

        text = ("⚠️ Se il nome non è corretto, è possibile che ci sia un problema con l'API di Google Play.\n\n"
                "🔸 Contatta @AleLntr o <u>invia un altro link</u>.")

        keyboard = [
            [
                InlineKeyboardButton(text="🆘 Scrivi ad @AleLntr", url="https://t.me/AleLntr")
            ],
            [
                InlineKeyboardButton(text="🔙 Torna Indietro",
                                     callback_data=f"back_to_main_settings {update.effective_message.id}")
            ]
        ]

        await parse_conversation_message(context=context, data={
            "chat_id": update.effective_chat.id,
            "message_id": update.effective_message.message_id,
            "text": text,
            "reply_markup": InlineKeyboardMarkup(keyboard)
        })

        return SEND_LINK


async def set_app(update: Update, context: CallbackContext):
    if update.callback_query and update.callback_query.data == "confirm_app_to_edit":
        if "edit_message" in context.chat_data:
            await delete_message(context=context, chat_id=update.effective_chat.id,
                                 message_id=context.chat_data["edit_message"])
            del context.chat_data["edit_message"]
        ap = context.bot_data["apps"][context.chat_data["app_index_to_edit"]]
        context.chat_data["setting_app"] = {
            "app_name": ap["app_name"],
            "app_link": ap["app_link"],
            "current_version": ap["current_version"],
            "last_update": ap["last_update"],
            "app_id": ap["app_id"]
        }

        context.chat_data["editing"] = True

    if update.callback_query and update.callback_query.data.startswith("edit_app_from_check"):
        index = update.callback_query.data.split(" ")[1]
        context.chat_data["app_index_to_edit"] = index
        ap = context.bot_data["apps"][index]
        context.chat_data["setting_app"] = {
            "app_name": ap["app_name"],
            "app_link": ap["app_link"],
            "current_version": ap["current_version"],
            "last_update": ap["last_update"],
            "app_id": ap["app_id"]
        }

        context.chat_data["editing"] = True

    adding = False if "editing" in context.chat_data or (
            update.callback_query and update.callback_query.data.startswith("edit_app_from_check")
    ) else True

    if update.callback_query and (update.callback_query.data == "app_name_from_link_correct" or
                                  update.callback_query.data.startswith("interval_incorrect") or
                                  update.callback_query.data == "confirm_app_to_edit" or
                                  update.callback_query.data.startswith("edit_app_from_check")):

        # inizio procedura di settaggio
        text = ("🪛 <b>App Set Up</b>\n\n"
                "🔸 <u>Intervallo di Controllo</u> – L'intervallo tra due aggiornamenti\n\n"
                "❔ <b>Format</b>\nFornisci una stringa nel formato ↙\n\n"
                "➡   <code>?m?d?h?min?s</code>\n\nsostituendo i <code>?</code> con i "
                "valori corrispondenti di:\n\n"
                "\t🔹 <code>m</code> – Mesi\n"
                "\t🔹 <code>d</code> – Giorni\n"
                "\t🔹 <code>h</code> – Ore\n"
                "\t🔹 <code>min</code> – Minuti\n"
                "\t🔹 <code>s</code> – Secondi\n\n"
                "Inserisci tutti i valori corrispondenti anche se nulli.\n\n "
                "<b>Esempio</b> 🔎 – <code>0m2d0h15min0s</code>\n\n"
                "🔸 Fornisci l'intervallo che desideri")

        context.chat_data["message_to_delete"] = update.effective_message.id

        keyboard = [
            [InlineKeyboardButton(text="⚡️ Use Defaults", callback_data=f"set_default_values")]
        ] if adding else [
            [InlineKeyboardButton(text="⚡️ Use Defaults", callback_data=f"edit_set_default_values")]
        ]

        sleep(1)

        message_id = await parse_conversation_message(context=context,
                                                      data={
                                                          "chat_id": update.effective_chat.id,
                                                          "message_id": update.effective_message.id,
                                                          "text": text,
                                                          "reply_markup": InlineKeyboardMarkup(keyboard)
                                                      })
        if message_id != update.effective_message.id:
            context.chat_data["message_to_delete"] = message_id

        return SET_INTERVAL

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    sleep(1)

    if adding:
        if update.callback_query and update.callback_query.data == "set_default_values":
            context.bot_data["apps"][str(len(context.bot_data["apps"]) + 1)] = {
                "app_name": context.chat_data["setting_app"]["app_name"],
                "app_link": context.chat_data["setting_app"]["app_link"],
                "current_version": context.chat_data["setting_app"]["current_version"],
                "last_update": context.chat_data["setting_app"]["last_update"],
                "app_id": context.chat_data["setting_app"]["app_id"],
                "last_check_time": None,
                "suspended": False,
                "check_interval": context.bot_data["settings"]["default_check_interval"],
                "send_on_check": context.bot_data["settings"]["default_send_on_check"]
            }

            del context.chat_data["setting_app"]

            await schedule_job_and_send_settled_app_message(update, context)
            return ConversationHandler.END

    else:
        if update.callback_query and update.callback_query.data == "edit_set_default_values":
            index = context.chat_data["app_index_to_edit"]
            context.bot_data["apps"][index]["check_interval"] = context.bot_data["settings"]["default_check_interval"]
            context.bot_data["apps"][index]["send_on_check"] = context.bot_data["settings"]["default_send_on_check"]
            await schedule_job_and_send_settled_app_message(update, context)
            return ConversationHandler.END

    if not update.callback_query:
        try:
            # noinspection DuplicatedCode
            months = int(update.message.text.split('m')[0])
            days = int(update.message.text.split('d')[0].split('m')[1])
            hours = int(update.message.text.split('h')[0].split('d')[1])
            minutes = int(update.message.text.split('min')[0].split('h')[1])
            seconds = int(update.message.text.split('s')[0].split('min')[1])

        except ValueError:
            text = ("❌ <b>Usa il formato indicato</b>, non aggiungere, togliere o cambiare lettere."
                    "\n\n🔎 <code>#m#d#h#min#s</code>")
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=text, parse_mode="HTML")
            return 2
        else:
            if "message_to_delete" in context.chat_data:
                await schedule_messages_to_delete(context=context,
                                                  messages={
                                                      int(update.effective_message.id): {
                                                          "time": 2.5,
                                                          "chat_id": update.effective_chat.id
                                                      },
                                                      int(context.chat_data["message_to_delete"]): {
                                                          "time": 2,
                                                          "chat_id": update.effective_chat.id
                                                      }
                                                  })
                del context.chat_data["message_to_delete"]

            context.chat_data["setting_app"]["check_interval"] = {
                "input": {
                    "days": days,
                    "months": months,
                    "seconds": seconds,
                    "minutes": minutes,
                    "hours": hours
                },
                "timedelta": timedelta(days=days + months * 30, seconds=seconds, minutes=minutes, hours=hours)
            }

            # noinspection DuplicatedCode
            text = (f"❓ Conferma se l'intervallo indicato è corretto.\n\n"
                    f"▫️ <code>{months}</code> mesi\n"
                    f"▫️ <code>{days}</code> giorni\n"
                    f"▫️ <code>{hours}</code> ore\n"
                    f"▫️ <code>{minutes}</code> minuti\n"
                    f"▫️ <code>{seconds}</code> secondi")

            message = await context.bot.send_message(chat_id=update.effective_chat.id,
                                                     text=text, parse_mode="HTML")

            keyboard = [
                [
                    InlineKeyboardButton(text="✅ È corretto.",
                                         callback_data=f"interval_correct {message.id}"),
                    InlineKeyboardButton(text="❌ Non è corretto.",
                                         callback_data=f"interval_incorrect {message.id}")
                ],
                [
                    InlineKeyboardButton(text="🔙 Torna Indietro", callback_data=f"back_to_main_settings {message.id}")
                ]
            ]

            await context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                                        message_id=message.id,
                                                        reply_markup=InlineKeyboardMarkup(keyboard))

            if "message_to_delete" in context.chat_data:
                await delete_message(context=context, chat_id=update.effective_chat.id,
                                     message_id=context.chat_data["message_to_delete"])
                del context.chat_data["message_to_delete"]

            return CONFIRM_INTERVAL

    if update.callback_query and update.callback_query.data.startswith("interval_correct"):
        await delete_message(context=context,
                             chat_id=update.effective_chat.id,
                             message_id=int(update.callback_query.data.split(" ")[1]))

        text = ("🪛 <b>App Set Up</b>\n\n"
                "🔸 <u>Send On Check</u> – Scegli se ti verrà mandato un messaggio: <b>solo quando viene trovato"
                " un aggiornamento</b> di questa app (<code>False</code>) "
                "o <b>ad ogni controllo</b> (<code>True</code>)")

        keyboard = [
            [
                InlineKeyboardButton(text="✅ True", callback_data=f"send_on_check_true"),
                InlineKeyboardButton(text="❌ False", callback_data=f"send_on_check_false")
            ]
        ]

        await context.bot.send_chat_action(chat_id=update.effective_chat.id,
                                           action=ChatAction.TYPING)
        context.job_queue.run_once(callback=job_queue.scheduled_send_message,
                                   data={
                                       "chat_id": update.effective_chat.id,
                                       "text": text,
                                       "keyboard": keyboard
                                   },
                                   when=1.5)

        return SEND_ON_CHECK

    if update.callback_query and update.callback_query.data.startswith("send_on_check"):
        if adding:
            context.bot_data["apps"][str(len(context.bot_data["apps"]) + 1)] = {
                "app_name": context.chat_data["setting_app"]["app_name"],
                "app_link": context.chat_data["setting_app"]["app_link"],
                "current_version": context.chat_data["setting_app"]["current_version"],
                "last_update": context.chat_data["setting_app"]["last_update"],
                "app_id": context.chat_data["setting_app"]["app_id"],
                "last_check": None,
                "suspended": False
            }

            ap = context.bot_data["apps"][str(len(context.bot_data["apps"]))]
        else:
            ap = context.bot_data["apps"][context.chat_data["app_index_to_edit"]]

        ap["check_interval"] = context.chat_data["setting_app"]["check_interval"]

        ap["next_check"] = (datetime.now(pytz.timezone('Europe/Rome')) +
                            context.chat_data["setting_app"]["check_interval"]["timedelta"])

        ap["send_on_check"] = True if update.callback_query.data == "send_on_check_true" else False

        bot_logger.info(f"App {ap["app_name"]} ({ap["app_id"]}) Settled Successfully -> "
                        f"Interval: "
                        f"{ap["check_interval"]["input"]["months"]}months "
                        f"{ap["check_interval"]["input"]["days"]}days "
                        f"{ap["check_interval"]["input"]["hours"]}hours "
                        f"{ap["check_interval"]["input"]["minutes"]}minutes "
                        f"{ap["check_interval"]["input"]["seconds"]}seconds – Send On Check: "
                        f"{ap["send_on_check"]}")

        if "setting_app" in context.chat_data:
            del context.chat_data["setting_app"]

    await schedule_job_and_send_settled_app_message(update, context)

    return ConversationHandler.END


async def edit_app(update: Update, context: CallbackContext):
    if update.callback_query and update.callback_query.data == "edit_app":
        if "edit_message" in context.chat_data:
            await delete_message(context=context, chat_id=update.effective_chat.id,
                                 message_id=context.chat_data["edit_message"])
            del context.chat_data["edit_message"]
        if len(context.bot_data["apps"]) == 0:
            text = ("✏ <b>Edit App</b>\n\n"
                    "ℹ Non hai applicazioni nell'elenco.\n\n"
                    "🔸 Scegli un'opzione")
            keyboard = [
                [
                    InlineKeyboardButton(text="➕ Aggiungi App", callback_data="add_app"),
                    InlineKeyboardButton(text="🔙 Torna indietro", callback_data="back_to_main_settings")
                ]
            ]
            await parse_conversation_message(context=context,
                                             data={
                                                 "chat_id": update.effective_chat.id,
                                                 "text": text,
                                                 "reply_markup": InlineKeyboardMarkup(keyboard),
                                                 "message_id": update.effective_message.message_id
                                             })
            return ConversationHandler.END

        text = ("✏ <b>Edit App</b>\n\n"
                "🗃 <b>Elenco Applicazioni</b>\n\n")

        for ap in context.bot_data["apps"]:
            a = context.bot_data["apps"][ap]
            text += (f"  {ap}. <i>{a["app_name"]}</i>\n"
                     f"      <u>Check Interval</u> "
                     f"<code>{a['check_interval']['input']['months']}m</code>"
                     f"<code>{a['check_interval']['input']['days']}d</code>"
                     f"<code>{a['check_interval']['input']['hours']}h</code>"
                     f"<code>{a['check_interval']['input']['minutes']}min</code>"
                     f"<code>{a['check_interval']['input']['seconds']}s</code>\n"
                     f"      <u>Send On Check</u> <code>{a['send_on_check']}</code>\n\n")

        text += "🔸 Scegli un'applicazione digitando il <u>numero corrispondente</u> o il <u>nome</u>"

        await parse_conversation_message(context, data={
            "chat_id": update.effective_chat.id,
            "text": text,
            "message_id": update.effective_message.message_id,
            "reply_markup": None
        })

        context.chat_data["edit_message"] = update.effective_message.message_id

        return EDIT_SELECT_APP

    if not update.callback_query and update.effective_message:
        if "message_to_delete" in context.chat_data:
            await schedule_messages_to_delete(context=context,
                                              messages={
                                                  int(context.chat_data["message_to_delete"]): {
                                                      "chat_id": update.effective_chat.id,
                                                      "time": 2
                                                  }
                                              })

            del context.chat_data["message_to_delete"]

        app_names = create_edit_app_list(context.bot_data)
        message = update.effective_message

        if not message.text.strip().isnumeric():
            if message.text.lower() not in app_names:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                sleep(1)
                message = await context.bot.send_message(chat_id=update.effective_chat.id,
                                                         text="🔴 <b>App Not Found</b>\n\n"
                                                              "🔸 Scegli un'applicazione dell'elenco",
                                                         parse_mode='HTML')

                keyboard = [
                    [InlineKeyboardButton(text="🔙 Torna Indietro",
                                          callback_data=f"back_to_main_settings {message.id}")]
                ]

                await context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                                            message_id=message.id,
                                                            reply_markup=InlineKeyboardMarkup(keyboard))

                await schedule_messages_to_delete(context=context,
                                                  messages={
                                                      str(update.effective_message.id): {
                                                          "time": 2.5,
                                                          "chat_id": update.effective_chat.id
                                                      }
                                                  })

                context.chat_data["message_to_delete"] = message.id
                return EDIT_SELECT_APP

        if (message.text.strip().isnumeric() and
                (int(message.text.strip()) > len(app_names) or int(message.text.strip()) < 0)):
            text = "🔴 <b>Invalid Index</b>\n\n🔸 Fornisci un indice valido"

            await parse_conversation_message(context=context,
                                             data={
                                                 "chat_id": update.effective_chat.id,
                                                 "text": text,
                                                 "message_id": -1,
                                                 "reply_markup": None
                                             })

            context.chat_data["message_to_delete"] = message.id

            return EDIT_SELECT_APP

        await schedule_messages_to_delete(context=context,
                                          messages={
                                              update.effective_message.id: {
                                                  "chat_id": update.effective_chat.id,
                                                  "time": 2
                                              }
                                          })

        context.chat_data["app_index_to_edit"] = str(message.text.strip())

        for el in app_names:
            if message.text.lower() == el:
                context.chat_data["app_index_to_edit"] = str(app_names.index(el) + 1)
                break

        text = (f"🔵 <b>App Found</b>\n\n"
                f"▶️ <code>"
                f"{context.bot_data["apps"][str(context.chat_data["app_index_to_edit"])]["app_name"]}"
                f"</code>\n\n"
                f"🔸 È l'applicazione che vuoi modificare?")

        keyboard = [
            [
                InlineKeyboardButton(text="⚪️ Si", callback_data="confirm_app_to_edit"),
                InlineKeyboardButton(text="⚫️ No", callback_data="edit_app")
            ]
        ]

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        sleep(1)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=text,
                                       reply_markup=InlineKeyboardMarkup(keyboard),
                                       parse_mode='HTML')

        return EDIT_CONFIRM_APP


async def remove_app(update: Update, context: CallbackContext):
    if (update.callback_query and (update.callback_query.data == "delete_app"
                                   or update.callback_query.data == "cancel_remove")):
        if "message_to_delete" in context.chat_data:
            await delete_message(context=context, chat_id=update.effective_chat.id,
                                 message_id=context.chat_data["message_to_delete"])
            del context.chat_data["message_to_delete"]

        if len(context.bot_data["apps"]) == 0:
            text = ("➖ <b>Remove App</b>\n\n"
                    "ℹ Non hai applicazioni nell'elenco.\n\n"
                    "🔸 Scegli un'opzione")
            keyboard = [
                [
                    InlineKeyboardButton(text="➕ Aggiungi App", callback_data="add_app"),
                    InlineKeyboardButton(text="🔙 Torna indietro", callback_data="back_to_main_settings")
                ]
            ]

            await parse_conversation_message(context=context, data={
                "chat_id": update.effective_chat.id,
                "text": text,
                "message_id": update.effective_message.id,
                "reply_markup": InlineKeyboardMarkup(keyboard)
            })

            return ConversationHandler.END

        text = ("♻️ <b>Remove App</b>\n\n"
                "🗃 <b>Elenco Applicazioni</b>\n\n")

        for ap in context.bot_data["apps"]:
            a = context.bot_data["apps"][ap]
            text += f"  {ap}. <i>{a["app_name"]}</i>\n"

        text += "\n🔸 Scegli un'applicazione da rimuovere indicando l'<u>indice</u> o il <u>nome</u>"
        message_id = await parse_conversation_message(context=context,
                                                      data={
                                                          "chat_id": update.effective_chat.id,
                                                          "text": text,
                                                          "message_id": update.effective_message.id,
                                                          "reply_markup": None
                                                      })

        context.chat_data["select_app_message"] = message_id

        return DELETE_APP_SELECT

    if not update.callback_query:
        if "message_to_delete" in context.chat_data:
            await delete_message(context=context, chat_id=update.effective_chat.id,
                                 message_id=context.chat_data["message_to_delete"])
            del context.chat_data["message_to_delete"]

        if not update.message.text.strip().isnumeric():
            if index := await get_app_from_string(update.message.text.strip().lower(), context):
                ap = context.bot_data["apps"][index]
                context.chat_data["app_index_to_delete"] = index
                text = (f"🔵 <b>App Found</b>\n\n"
                        f"🔸 App Name: <code>{ap["app_name"]}</code>\n\n"
                        f"🔹 Vuoi rimuovere questa applicazione?")
                keyboard = [
                    [
                        InlineKeyboardButton(text="🚮 Si", callback_data="confirm_remove"),
                        InlineKeyboardButton(text="🚯 No", callback_data="cancel_remove")
                    ],
                    [
                        InlineKeyboardButton(text="⏸ Sospendi", callback_data="suspend_app")
                    ]
                ]

                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                sleep(1)
                message = await context.bot.send_message(chat_id=update.effective_chat.id,
                                                         text=text,
                                                         reply_markup=InlineKeyboardMarkup(keyboard),
                                                         parse_mode='HTML')
                context.chat_data["message_to_delete"] = message.id

                return DELETE_APP_CONFIRM

            text = ("🔴 <b>App Not Found</b>\n\n"
                    "🔸 Scegli un'applicazione da rimuovere indicando l'<u>indice</u> o il <u>nome</u>")

            message_id = await parse_conversation_message(context=context,
                                                          data={
                                                              "chat_id": update.effective_chat.id,
                                                              "text": text,
                                                              "message_id": -1,
                                                              "reply_markup": None
                                                          })

            context.chat_data["message_to_delete"] = message_id

            return DELETE_APP_SELECT

        else:
            if (index := int(update.message.text.strip())) > len(context.bot_data["apps"]) or index < 0:
                text = "❌ Inserisci un indice valido"

                message_id = await parse_conversation_message(context=context,
                                                              data={
                                                                  "chat_id": update.effective_chat.id,
                                                                  "text": text,
                                                                  "message_id": -1,
                                                                  "reply_markup": None
                                                              })

                context.chat_data["message_to_delete"] = message_id

                return DELETE_APP_SELECT
            else:
                ap = context.bot_data["apps"][index := update.message.text.strip()]
                context.chat_data["app_index_to_delete"] = index

                text = (f"🔵 <b>App Found</b>\n\n"
                        f"🔸 App Name: <code>{ap["app_name"]}</code>\n\n"
                        f"🔹 Vuoi rimuovere questa applicazione?")
                keyboard = [
                    [
                        InlineKeyboardButton(text="🚮 Si", callback_data="confirm_remove"),
                        InlineKeyboardButton(text="🚯 No", callback_data="cancel_remove")
                    ],
                    [
                        InlineKeyboardButton(text="⏸ Sospendi", callback_data="suspend_app")
                    ]
                ]

                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                sleep(1)
                message = await context.bot.send_message(chat_id=update.effective_chat.id,
                                                         text=text,
                                                         reply_markup=InlineKeyboardMarkup(keyboard),
                                                         parse_mode='HTML')
                context.chat_data["message_to_delete"] = message.id

                return DELETE_APP_CONFIRM

    if update.callback_query and update.callback_query.data == "confirm_remove":
        if "select_app_message" in context.chat_data:
            await delete_message(context=context, chat_id=update.effective_chat.id,
                                 message_id=context.chat_data["select_app_message"])
            del context.chat_data["select_app_message"]
        if "message_to_delete" in context.chat_data:
            await delete_message(context=context, chat_id=update.effective_chat.id,
                                 message_id=context.chat_data["message_to_delete"])
            del context.chat_data["message_to_delete"]

        app_name = context.bot_data["apps"][context.chat_data["app_index_to_delete"]]["app_name"]
        app_id = context.bot_data["apps"][context.chat_data["app_index_to_delete"]]["app_id"]

        for ap in context.bot_data["apps"]:
            if int(ap) < int(context.chat_data["app_index_to_delete"]):
                continue
            elif int(ap) < len(context.bot_data["apps"]):
                context.bot_data["apps"][ap] = context.bot_data["apps"][str(int(ap) + 1)]
        del context.bot_data["apps"][str(len(context.bot_data["apps"]))]
        del context.chat_data["app_index_to_delete"]

        bot_logger.info(f"App {app_name} ({app_id}) deleted successfully")

        text = ("✔ <b>App Removed Successfully</b>\n\n"
                "🔸 Scegli un'opzione")
        keyboard = [
            [
                InlineKeyboardButton(text="➖ Rimuovi Altra App", callback_data="delete_app"),
                InlineKeyboardButton(text="🔙 Torna indietro", callback_data="back_to_main_settings")
            ]
        ]

        await parse_conversation_message(context=context, data={
            "chat_id": update.effective_chat.id,
            "text": text,
            "message_id": update.effective_message.id,
            "reply_markup": InlineKeyboardMarkup(keyboard)
        })

        return ConversationHandler.END


async def suspend_app(update: Update, context: CallbackContext):
    if update.callback_query and len(li := update.callback_query.data.split(" ")) > 1:
        context.bot_data["apps"][str(li[1])]["suspended"] = True

        text = (f"⏸ <b>Sospendi App</b>\n\n"
                f"🔹  App <code>{context.bot_data["apps"][li[1]]["app_name"]} sospesa: non riceverai più aggiornamenti."
                f" Puoi riattivarla dalle impostazioni.")


async def see_app_settings(update: Update, context: CallbackContext):
    if (index := update.callback_query.data.split(" ")[1]) in context.bot_data["apps"]:
        ap = context.bot_data["apps"][index]

        text = (f"🔍 <b>App Settings</b>\n\n"
                f"  🔹App Name: <code>{ap["app_name"]}</code>\n"
                f"  🔹Check Interval: "
                f"<code>{ap["check_interval"]["input"]["months"]}m</code>"
                f"<code>{ap["check_interval"]["input"]["days"]}d</code>"
                f"<code>{ap["check_interval"]["input"]["hours"]}h</code>"
                f"<code>{ap["check_interval"]["input"]["minutes"]}min</code>"
                f"<code>{ap["check_interval"]["input"]["seconds"]}s</code>\n"
                f"  🔹Send On Check: <code>{ap["send_on_check"]}</code>\n\n"
                f"🔸 Scegli un'opzione")

        message = await context.bot.send_message(chat_id=update.effective_chat.id,
                                                 text=text,
                                                 parse_mode='HTML')

        keyboard = [
            [
                InlineKeyboardButton(text="✏ Modifica", callback_data=f"edit_app_from_check {index}"),
                InlineKeyboardButton(text="🗑 Chiudi", callback_data=f"delete_check_message {message.id}")
            ]
        ]

        await context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                                    message_id=message.id,
                                                    reply_markup=InlineKeyboardMarkup(keyboard))


async def parse_conversation_message(context: CallbackContext, data: dict):
    check_dict_keys(data, ["chat_id", "message_id", "text", "reply_markup"])

    chat_id, message_id, text, reply_markup = data["chat_id"], data["message_id"], data["text"], data["reply_markup"]

    keyboard = [
        [InlineKeyboardButton(text="🔙 Torna Indietro",
                              callback_data=f"back_to_main_settings {message_id}")]
    ]

    reply_markup = reply_markup if reply_markup else InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.edit_message_text(chat_id=chat_id,
                                            message_id=message_id,
                                            text=text,
                                            reply_markup=(reply_markup if reply_markup is not False else None),
                                            parse_mode="HTML")
        return message_id

    except telegram.error.BadRequest as e:
        settings_logger.warning(f"Not able to edit message: {e}. A new one will be sent.")

        # se il messaggio è stato rimosso e ne viene mandato un altro, i tasti che contengono un id scatenerebbero
        # un'eccezione nelle fasi successive, ma il 'try-except...pass' ovvia al problema.
        message = await context.bot.send_message(chat_id=chat_id,
                                                 text=text,
                                                 reply_markup=reply_markup if reply_markup is not False else None,
                                                 parse_mode="HTML")

        if "close_button" in data:
            button = keyboard
            for i in data["close_button"][:-1]:
                button = button[i - 1]

            # noinspection PyTypeChecker
            button[data["close_button"][-1] - 1] = InlineKeyboardButton(
                text="🔙 Torna Indietro",
                callback_data=f"back_to_main_settings {message_id}"
            )

            await context.bot.edit_message_reply_markup(chat_id=chat_id,
                                                        message_id=message.id,
                                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return message.id


async def schedule_job_and_send_settled_app_message(update: Update, context: CallbackContext):
    added = True if "editing" not in context.chat_data else False

    if added:
        ap = context.bot_data["apps"][str(len(context.bot_data["apps"]))]
    else:
        index = context.chat_data["app_index_to_edit"]
        ap = context.bot_data["apps"][index]
        del context.chat_data["app_index_to_edit"]
        del context.chat_data["editing"]

    ap["next_check"] = {}
    ap["next_check"] = datetime.now(pytz.timezone('Europe/Rome')) + ap["check_interval"]["timedelta"]

    text = (f"☑️ <b>App Settled Successfully</b>\n\n"
            f"🔹<u>Check Interval</u> ➡ "
            f"<code>"
            f"{ap["check_interval"]["input"]["months"]}m"
            f"{ap["check_interval"]["input"]["days"]}d"
            f"{ap["check_interval"]["input"]["hours"]}h"
            f"{ap["check_interval"]["input"]["minutes"]}"
            f"min"
            f"{ap["check_interval"]["input"]["seconds"]}s"
            f"</code>\n"
            f"🔹<u>Send On Check</u> ➡ "
            f"<code>{ap["send_on_check"]}</code>\n\n"
            f"🔸 <u>Next Check</u> ➡ <code>{ap["next_check"].strftime('%d %B %Y – %H:%M:%S')}</code>"
            f"\n\n")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id,
                                       action=ChatAction.TYPING)

    if added:
        button = InlineKeyboardButton(text="➕ Aggiungi Altra App", callback_data="add_app")
    else:
        button = InlineKeyboardButton(text="✏ Modifica Altra App", callback_data="edit_app")

    keyboard = [
        [
            button,
            InlineKeyboardButton(text="🔙 Torna Indietro", callback_data="back_to_main_settings")
        ]
    ]

    context.job_queue.run_once(callback=job_queue.scheduled_send_message,
                               data={
                                   "chat_id": update.effective_chat.id,
                                   "text": text,
                                   "message_id": update.effective_message.id,
                                   "keyboard": keyboard
                               },
                               when=1.5)

    if not added:
        jobs = context.job_queue.get_jobs_by_name(ap["app_name"])
        if len(jobs) > 0:
            for job in jobs:
                job.schedule_removal()

    # noinspection PyUnboundLocalVariable
    context.job_queue.run_repeating(
        callback=job_queue.scheduled_app_check,
        interval=ap["check_interval"]["timedelta"],
        chat_id=update.effective_chat.id,
        name=ap["app_name"],
        data={
            "app_link": ap["app_link"],
            "app_id": ap["app_id"],
            "app_index": str(len(context.bot_data["apps"])) if added else index
        }
    )

    bot_logger.info(f"Repeating Job for app {ap["app_name"]} Scheduled Successfully "
                    f"– Next Check at {(datetime.now(pytz.timezone('Europe/Rome')) 
                                        + ap["check_interval"]["timedelta"]).strftime("%d %b %Y - %H:%M:%S")}")

    if not added:
        return EDIT_CONFIRM_APP

    if "editing" in context.chat_data:
        del context.chat_data["editing"]

    return ConversationHandler.END


async def schedule_messages_to_delete(context: CallbackContext, messages: dict):
    for message in messages:
        check_dict_keys(messages[message], ["time", "chat_id"])
        time, chat_id = messages[message]["time"], messages[message]["chat_id"]

        context.job_queue.run_once(callback=job_queue.scheduled_delete_message,
                                   data={
                                       "message_id": int(message),
                                       "chat_id": chat_id
                                   },
                                   when=time)


async def get_app_details_with_link(link: str):
    res = requests.get(link)
    if res.status_code != 200:
        settings_logger.warning(f"Not able to gather link {link}: {res.reason}")
        return None
    try:
        id_app = link.split("id=")[1].split('&')[0]
        app_details = app(app_id=id_app)
    except IndexError as e:
        return e
    except NotFoundError as e:
        return e
    else:
        return app_details


async def delete_callback_query_message(update: Update, context: CallbackContext):
    try:
        await context.bot.delete_message(chat_id=os.getenv("MY_ID"),
                                         message_id=int(update.callback_query.data.split(" ")[1]))
    except telegram.error.BadRequest:
        pass


async def delete_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    try:
        await context.bot.delete_message(chat_id=chat_id,
                                         message_id=message_id)
    except telegram.error.BadRequest:
        pass


async def get_app_from_string(string: str, context: CallbackContext):
    whitelist = set('abcdefghijklmnopqrstuvwxyz ')
    for a in context.bot_data["apps"]:
        if string == ''.join(filter(whitelist.__contains__, context.bot_data["apps"][a]["app_name"].lower())):
            return a
    return None


def check_dict_keys(d: dict, keys: list):
    mancanti = [key for key in keys if key not in d]
    if len(mancanti) != 0:
        raise Exception(f"Missing key(s): {mancanti} in dictionary {d}")


def create_edit_app_list(bot_data: dict) -> list:
    whitelist = set('abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    app_names = []
    if "apps" in bot_data:
        for a in bot_data["apps"]:
            app_names.append(''.join(filter(whitelist.__contains__, str(bot_data["apps"][a]["app_name"]).lower())))

    return app_names or []
