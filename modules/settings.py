from telegram.constants import ChatAction
from telegram.ext import CallbackContext, ConversationHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import timedelta

import telegram

import job_queue


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
    try:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                            message_id=update.message.message_id,
                                            text=text)
    pass


async def close_menu(update: Update, context: CallbackContext):
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id,
                                         message_id=int(update.callback_query.data.split(" ")[1]))
    except telegram.error.BadRequest:
        pass
    finally:
        return ConversationHandler.END
