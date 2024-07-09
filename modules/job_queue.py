from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import telegram

import logging

job_queue_logger = logging.getLogger("job_queue_logger")
job_queue_logger.setLevel(logging.WARN)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler(filename='./misc/logs/logs.txt')
file_handler.setFormatter(formatter)
job_queue_logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
job_queue_logger.addHandler(console_handler)


async def scheduled_send_message(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    if "chat_id" not in data or "text" not in data:
        job_queue_logger.warning("'chat_id' or 'message_id' are missing in Job data.")
        raise Exception("Missing 'chat_id' or 'message_id' in job data.")

    if "message_id" in data:
        try:
            await context.bot.delete_message(chat_id=data["chat_id"], message_id=data["message_id"])
        except telegram.error.BadRequest as e:
            job_queue_logger.warning(f"Failed to delete message: {e}.")

    if "keyboard" in data:
        if "close_button" in data:
            check = isinstance(data["close_button"][1], list)
            close_buttons = []
            if check:
                for button in data["close_button"]:
                    close_button = data["keyboard"]
                    for i in button:
                        if i > len(close_button):
                            job_queue_logger.error("Close button id is greater than the number of buttons in"
                                                   " the keyboard.")
                            raise telegram.error.BadRequest("Close button id is greater than the number of buttons in "
                                                            "the keyboard.")
                        close_button = close_button[i - 1]
                    close_buttons.append(close_button)
            else:
                close_button = data["keyboard"]
                for i in data["close_button"]:
                    if i > len(close_button):
                        job_queue_logger.error("Close button id is greater than the number of buttons in the keyboard.")
                        raise telegram.error.BadRequest("Close button id is greater than the number of buttons in "
                                                        "the keyboard.")
                    close_button = close_button[i - 1]
                close_buttons.append(close_button)

    try:
        web_preview = (not data["web_preview"] if "web_preview" in data else None)
        if "close_button" in data:
            message = await context.bot.send_message(chat_id=data["chat_id"],
                                                     text=data["text"],
                                                     parse_mode="HTML",
                                                     disable_web_page_preview=web_preview)
            # noinspection PyUnboundLocalVariable
            for counter, button in enumerate(close_buttons, start=1):
                # noinspection PyUnboundLocalVariable
                close_buttons[counter - 1] = InlineKeyboardButton(text=close_buttons[counter - 1].text,
                                                                  callback_data=close_buttons[counter - 1].
                                                                  callback_data.format(message.id))
            # noinspection PyUnboundLocalVariable
            if check:
                for counter, button in enumerate(data["close_button"], start=1):
                    button_to_change = data["keyboard"]
                    parent = None
                    for i in button:
                        parent = button_to_change
                        button_to_change = button_to_change[i - 1]
                    final_index = button[-1] - 1
                    # noinspection PyUnboundLocalVariable
                    parent[final_index] = close_buttons[counter - 1]
            else:
                button_to_change = data["keyboard"]
                parent = None
                for i in data["close_button"]:
                    parent = button_to_change
                    button_to_change = button_to_change[i - 1]
                final_index = data["close_button"][-1] - 1
                # noinspection PyUnboundLocalVariable
                parent[final_index] = close_buttons[0]

            reply_markup = InlineKeyboardMarkup(data["keyboard"])
            await context.bot.edit_message_reply_markup(chat_id=data["chat_id"], message_id=message.id,
                                                        reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=data["chat_id"], text=data["text"], parse_mode="HTML",
                                           reply_markup=(InlineKeyboardMarkup(data["keyboard"])
                                                         if "keyboard" in data else None),
                                           disable_web_page_preview=web_preview)

    except telegram.error.TelegramError as e:
        job_queue_logger.error(f'Not able to perform scheduled action: {e}')


async def scheduled_edit_message(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    if "chat_id" not in data or "text" not in data or "message_id" not in data:
        job_queue_logger.warning("'chat_id' or 'message_id' or 'message_id' are missing in Job data.")
        raise Exception("Missing 'chat_id' or 'message_id' in job data.")

    message = await context.bot.send_message(text=".", chat_id=data["chat_id"])
    await context.bot.delete_message(chat_id=data["chat_id"], message_id=message.id)

    try:
        await context.bot.edit_message_text(text=data["text"],
                                            chat_id=data["chat_id"],
                                            message_id=data["message_id"],
                                            reply_markup=(InlineKeyboardMarkup(data["keyboard"]))
                                            if "keyboard" in data else None,
                                            parse_mode="HTML")
    except telegram.error.TelegramError as e:
        job_queue_logger.error(f'Not able to perform scheduled action: {e}')
