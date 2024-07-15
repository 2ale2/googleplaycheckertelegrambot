import logging
from datetime import timedelta, datetime
from logging import handlers

import requests
import telegram
from google_play_scraper import app
from google_play_scraper.exceptions import NotFoundError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, ConversationHandler

import job_queue

settings_logger = logging.getLogger("settings_logger")
settings_logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = handlers.RotatingFileHandler(filename="../misc/logs/settings.log",
                                            maxBytes=1024, backupCount=1)
file_handler.setFormatter(formatter)
settings_logger.addHandler(file_handler)

CHANGE_SETTINGS, MENAGE_APPS, LIST_LAST_CHECKS, MENAGE_APPS_OPTIONS, LIST_APPS, ADD_APP = range(6)

SEND_LINK, CONFIRM_APP_NAME = range(2)

SET_INTERVAL, CONFIRM_INTERVAL, SEND_ON_CHECK, SET_UP_ENDED = range(4)


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
            # noinspection DuplicatedCode
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
            # noinspection DuplicatedCode
            text = (f"❓ Conferma se l'intervallo indicato è corretto.\n\n"
                    f"▫️️ <code>{months}</code> mesi\n"
                    f"▫️ <code>{days}</code> giorni\n"
                    f"▫️ <code>{hours}</code> ore\n"
                    f"▫️ <code>{minutes}</code> minuti\n"
                    f"▫️ <code>{seconds}</code> secondi")
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
                "➡ <u>Default Send On Check</u> – Scegli se, di default, ti verrà mandato un messaggio <b>solo "
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

    await parse_conversation_message(context=context,
                                     data={
                                         "chat_id": update.effective_chat.id,
                                         "message_id": update.effective_message.message_id,
                                         "text": text,
                                         "reply_markup": InlineKeyboardMarkup(keyboard)}
                                     )

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
            for ap in context.bot_data["apps"]:
                text += f"  {ap}. {context.bot_data['apps'][str(ap)]["app_name"]}\n\n"

        text += "🔸Manda il link all'applicazione su Google Play"

        context.chat_data["message_to_delete"] = update.effective_message.id

        await parse_conversation_message(data={
            "chat_id": update.effective_chat.id,
            "message_id": update.effective_message.message_id,
            "text": text,
            "reply_markup": None
        }, context=context)

        return SEND_LINK

    not_cquery_message = update.effective_message if update.effective_message and not update.callback_query else None

    if not_cquery_message:
        if len(entities := not_cquery_message.entities) == 1 and entities[0].type == MessageEntity.URL:
            link = update.message.text[entities[0].offset:]
            res = requests.get(link)

            if res.status_code != 200:
                settings_logger.warning(f"Not able to gather link {link}: {res.reason}")
                text = (f"❌ A causa di un problema di rete, non riuscito a reperire il link che hai mandato.\n\n"
                        f"🔍 <i>Reason</i>\n{res.reason}\n\n"
                        f"🆘 Se il problema persiste, contatta @AleLntr\n\n"
                        f"🔸Puoi riprovare a mandare lo stesso link o cambiarlo")

                await parse_conversation_message(context=context,
                                                 data={
                                                     "chat_id": update.effective_chat.id,
                                                     "message_id": not_cquery_message.id,
                                                     "text": text,
                                                     "reply_markup": None
                                                 })

                return SEND_LINK

            app_details = await get_app_details_with_link(link=link)

            if not app_details:

                text = ("⚠️ Ho avuto problemi a reperire l'applicazione.\n\n"
                        "Potrebbe essere un problema di API o l'applicazione potrebbe essere stata rimossa.\n\n"
                        "🔸Contatta @AleLntr per risolvere il problema, o manda un altro link")

                await parse_conversation_message(context=context,
                                                 data={
                                                     "chat_id": update.effective_chat.id,
                                                     "message_id": not_cquery_message.message_id,
                                                     "text": text,
                                                     "reply_markup": None
                                                 })

                return SEND_LINK

            else:
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
                                  f"🔸Contatta @AleLntr per risolvere il problema")

                await parse_conversation_message(context=context, data={
                    "chat_id": update.effective_chat.id,
                    "message_id": not_cquery_message.message_id,
                    "text": text,
                    "reply_markup": InlineKeyboardMarkup(keyboard) if keyboard else None
                })

                if "message_to_delete" in context.chat_data:
                    # noinspection DuplicatedCode
                    await schedule_messages_to_delete(context=context,
                                                      messages={
                                                          str(not_cquery_message.id): {
                                                              "time": 2,
                                                              "chat_id": update.effective_chat.id,
                                                          },
                                                          str(context.chat_data["message_to_delete"]): {
                                                              "time": 2.5,
                                                              "chat_id": update.effective_chat.id,
                                                          }
                                                      })

                    del context.chat_data["message_to_delete"]

                return CONFIRM_APP_NAME

        else:
            keyboard = [
                [
                    InlineKeyboardButton(text="🔙 Torna Indietro",
                                         callback_data=f"back_to_main_settings {not_cquery_message.id}"),
                    InlineKeyboardButton(text="🆘 Contatta @AleLntr", url='https://t.me/AleLntr')
                ]
            ]
            text = "❌ Non hai mandato un link valido o hai mandato più di un link nello stesso messaggio."

            await parse_conversation_message(context=context,
                                             data={
                                                 "chat_id": update.effective_chat.id,
                                                 "message_id": not_cquery_message.message_id,
                                                 "text": text,
                                                 "reply_markup": InlineKeyboardMarkup(keyboard)
                                             })

            # noinspection DuplicatedCode
            await schedule_messages_to_delete(context=context,
                                              messages={
                                                  str(not_cquery_message.id): {
                                                      "time": 2,
                                                      "chat_id": update.effective_chat.id,
                                                  },
                                                  str(context.chat_data["message_to_delete"]): {
                                                      "time": 2.5,
                                                      "chat_id": update.effective_chat.id,
                                                  }
                                              })

            del context.chat_data["message_to_delete"]

            return SEND_LINK

    if update.callback_query and update.callback_query.data == "app_name_from_link_not_correct":
        text = ("⚠️ Se il nome non è corretto, è possibile che ci sia un problema con l'API di Google Play.\n\n"
                "🔸Contatta @AleLntr o <u>invia un altro link</u>.")

        keyboard = [
            [
                InlineKeyboardButton(text="🆘 Scrivi ad @AleLntr", url="https://t.me/AleLntr")
            ],
            InlineKeyboardButton(text="🔙 Torna Indietro",
                                 callback_data=f"back_to_main_settings")
        ]

        await parse_conversation_message(context=context, data={
            "chat_id": update.effective_chat.id,
            "message_id": not_cquery_message.message_id,
            "text": text,
            "reply_markup": InlineKeyboardMarkup(keyboard)
        })

        return SEND_LINK


async def set_app(update: Update, context: CallbackContext):
    if update.callback_query and (update.callback_query.data == "app_name_from_link_correct" or
                                  update.callback_query.data.startswith("interval_incorrect")):
        # inizio procedura di settaggio
        text = ("🪛 <b>App Set Up</b>\n\n"
                "🔸<u>Intervallo di Controllo</u> – L'intervallo tra due aggiornamenti\n\n"
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
                "🔸Fornisci l'intervallo che desideri")

        context.chat_data["message_to_delete"] = update.effective_message.id

        await parse_conversation_message(context=context,
                                         data={
                                             "chat_id": update.effective_chat.id,
                                             "message_id": update.effective_message.id,
                                             "text": text,
                                             "reply_markup": None
                                         })

        return SET_INTERVAL

    if not update.callback_query:
        try:
            # noinspection DuplicatedCode
            months = int(update.message.text.split('m')[0])
            days = int(update.message.text.split('d')[0].split('m')[1])
            hours = int(update.message.text.split('h')[0].split('d')[1])
            minutes = int(update.message.text.split('min')[0].split('h')[1])
            seconds = int(update.message.text.split('s')[0].split('min')[1])

            if "message_to_delete" in context.chat_data:
                await schedule_messages_to_delete(context=context,
                                                  messages={
                                                      str(update.effective_message.id): {
                                                          "time": 2.5,
                                                          "chat_id": update.effective_chat.id
                                                      },
                                                      str(context.chat_data["message_to_delete"]): {
                                                          "time": 2,
                                                          "chat_id": update.effective_chat.id
                                                      }
                                                  })
                del context.chat_data["message_to_delete"]

        except ValueError:
            text = ("❌ <b>Usa il formato indicato</b>, non aggiungere, togliere o cambiare lettere."
                    "\n\n🔎 <code>#m#d#h#min#s</code>")
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=text, parse_mode="HTML")
            return 2
        else:
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
                ]
            ]

            await context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                                        message_id=message.id,
                                                        reply_markup=InlineKeyboardMarkup(keyboard))

            return CONFIRM_INTERVAL

    if update.callback_query and update.callback_query.data.startswith("interval_correct"):
        if len(li := update.callback_query.data.split(" ")) > 1:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id,
                                                 message_id=int(li[1]))
            except telegram.error.BadRequest:
                pass

        text = ("🪛 <b>App Set Up</b>\n\n"
                "🔸<u>Send On Check</u> – Scegli se ti verrà mandato un messaggio: <b>solo quando viene trovato"
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
        context.bot_data["apps"][str(len(context.bot_data["apps"])+1)] = {
            "app_name": context.chat_data["setting_app"]["app_name"],
            "app_link": context.chat_data["setting_app"]["app_link"],
            "current_version": context.chat_data["setting_app"]["current_version"],
            "last_update": context.chat_data["setting_app"]["last_update"],
            "app_id": context.chat_data["setting_app"]["app_id"],
            "last_check": None,
            "last_check_time": None
        }

        context.bot_data["apps"][str(len(context.bot_data["apps"]))]["check_interval"] = (
            context.chat_data["setting_app"]["check_interval"])

        context.bot_data["apps"][str(len(context.bot_data["apps"]))]["next_check"] = (
                datetime.now() + context.chat_data["setting_app"]["check_interval"]["timedelta"])
        
        context.bot_data["apps"][str(len(context.bot_data["apps"]))]["send_on_check"] = True \
            if update.callback_query.data == "send_on_check_true" else False

        text = (f"☑️ <b>App Settled Successfully</b>\n\n"
                f"🔹<u>Check Interval</u> ➡ "
                f"<code>"
                f"{context.bot_data["apps"][str(len(context.bot_data["apps"]))]["check_interval"]["input"]["months"]}m"
                f"{context.bot_data["apps"][str(len(context.bot_data["apps"]))]["check_interval"]["input"]["days"]}d"
                f"{context.bot_data["apps"][str(len(context.bot_data["apps"]))]["check_interval"]["input"]["hours"]}h"
                f"{context.bot_data["apps"][str(len(context.bot_data["apps"]))]["check_interval"]["input"]["minutes"]}"
                f"min"
                f"{context.bot_data["apps"][str(len(context.bot_data["apps"]))]["check_interval"]["input"]["seconds"]}s"
                f"</code>\n"
                f"🔹<u>Send On Check</u> ➡ "
                f"<code>{str(context.bot_data["apps"][str(len(context.bot_data["apps"]))]["send_on_check"])}</code>"
                f"\n\n")

        keyboard = [
            [
                InlineKeyboardButton(text="➕ Aggiungi Altra App", callback_data="add_app"),
                InlineKeyboardButton(text="🔙 Torna Indietro",
                                     callback_data=f"back_to_main_settings {update.effective_message.id}")
            ]
        ]

        await parse_conversation_message(context=context,
                                         data={
                                             "chat_id": update.effective_chat.id,
                                             "message_id": update.effective_message.id,
                                             "text": text,
                                             "reply_markup": InlineKeyboardMarkup(keyboard)
                                         })
        context.bot_data["apps"][str(len(context.bot_data["apps"]))]["next_check"] = {}
        timed = context.bot_data["apps"][str(len(context.bot_data["apps"]))]["check_interval"]["timedelta"]
        context.bot_data["apps"][str(len(context.bot_data["apps"]))]["next_check"] = datetime.now() + timed

        context.job_queue.run_repeating(
            callback=job_queue.scheduled_app_check,
            interval=context.bot_data["apps"][str(len(context.bot_data["apps"]))]["check_interval"]["timedelta"],
            chat_id=update.effective_chat.id,
            name=context.bot_data["apps"][str(len(context.bot_data["apps"]))]["app_name"],
            data={
                "app_link": context.bot_data["apps"][str(len(context.bot_data["apps"]))]["app_link"],
                "app_id": context.bot_data["apps"][str(len(context.bot_data["apps"]))]["app_id"],
                "app_index": str(len(context.bot_data["apps"]))
            }
        )


async def parse_conversation_message(context: CallbackContext, data: dict):
    check_dict_keys(data, ["chat_id", "message_id", "text", "reply_markup"])

    chat_id, message_id, text, reply_markup = data["chat_id"], data["message_id"], data["text"], data["reply_markup"]

    keyboard = [
        [InlineKeyboardButton(text="🔙 Torna Indietro",
                              callback_data=f"back_to_main_settings {message_id}")]
    ]

    try:
        await context.bot.edit_message_text(chat_id=chat_id,
                                            message_id=message_id,
                                            text=text,
                                            reply_markup=(reply_markup
                                                          if reply_markup is not None
                                                          else InlineKeyboardMarkup(keyboard)
                                                          if reply_markup is not False else None),
                                            parse_mode="HTML")
    except telegram.error.BadRequest as e:
        settings_logger.warning(f"Not able to edit message: {e}\nA new one will be sent.")

        # se il messaggio è stato rimosso e ne viene mandato un altro, i tasti che contengono un id scatenerebbero
        # un'eccezione nelle fasi successive, ma il 'try-except...pass' ovvia al problema.
        await context.bot.send_message(chat_id=chat_id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode="HTML")


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
    id_app = link.split("id=")[1].split('&')[0]
    try:
        app_details = app(app_id=id_app)
    except NotFoundError as e:
        settings_logger.warning(f"Not able to find package '{id_app}': {e}")
        return None
    else:
        return app_details


def check_dict_keys(d: dict, keys: list):
    mancanti = [key for key in keys if key not in d]
    if len(mancanti) != 0:
        raise Exception(f"Missing key(s): {mancanti} in dictionary {d}")
