import os
import json
from datetime import datetime

import gspread
from dotenv import load_dotenv
from groq import AsyncGroq
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

client = AsyncGroq(api_key=GROQ_API_KEY)

gc = gspread.service_account(filename="credentials.json")
spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
worksheet = spreadsheet.sheet1


def note_keyboard(row_number):
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Note",
                callback_data=f"note:{row_number}",
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to FetchMeaningBot! 📚\n\n"
        "Send me any English word or phrase, and I'll give you its meaning "
        "and an example sentence.\n\n"
        "Use /getwords to view your vocabulary."
    )


async def add_note_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    row_number = int(query.data.split(":")[1])
    user_id = str(query.from_user.id)

    try:
        row = worksheet.row_values(row_number)

        if not row or row[0] != user_id:
            await query.message.reply_text(
                "❌ You cannot add a note to this entry."
            )
            return

        context.user_data["pending_note_row"] = row_number

        word = row[1] if len(row) > 1 else "this word"

        await query.message.reply_text(
            f"📝 Send me the note you'd like to save for *{word}*.\n\n"
            "Your note will be saved alongside the word.\n"
            "Send /cancel to cancel.",
            parse_mode="Markdown",
        )

    except Exception as e:
        print("Error opening note:", type(e).__name__, str(e)[:300])
        await query.message.reply_text(
            "Something went wrong while opening the note."
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pending_note_row", None)

    await update.message.reply_text(
        "❌ Note cancelled. Send me another word whenever you're ready."
    )


async def handle_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text:
        return

    pending_row = context.user_data.get("pending_note_row")

    if pending_row is not None:
        user_id = str(update.effective_user.id)

        try:
            row = worksheet.row_values(pending_row)

            if not row or row[0] != user_id:
                context.user_data.pop("pending_note_row", None)
                await update.message.reply_text(
                    "❌ I couldn't find that word in your vocabulary."
                )
                return

            worksheet.update_cell(pending_row, 7, text)

            word = row[1] if len(row) > 1 else "your word"

            context.user_data.pop("pending_note_row", None)

            await update.message.reply_text(
                f"✅ Note saved for *{word}*!\n\n"
                f"📝 {text}",
                parse_mode="Markdown",
            )
            return

        except Exception as e:
            print("Error saving note:", type(e).__name__, str(e)[:300])
            await update.message.reply_text(
                "Something went wrong while saving your note."
            )
            return

    word = text
    user_id = str(update.effective_user.id)

    await update.message.reply_text("Fetching meaning... 🔍")

    try:
        rows = worksheet.get_all_values()

        existing_word = None
        existing_row_number = None

        for row_number, row in enumerate(rows[1:], start=2):
            if (
                len(row) > 1
                and row[0] == user_id
                and row[1].strip().casefold() == word.casefold()
            ):
                existing_word = row
                existing_row_number = row_number
                break

        if existing_word:
            saved_word = existing_word[1]
            part_of_speech = existing_word[2] if len(existing_word) > 2 else ""
            meaning = existing_word[3] if len(existing_word) > 3 else ""
            example = existing_word[4] if len(existing_word) > 4 else ""

            message = (
                f"Word: {saved_word}\n"
                f"Part of Speech: {part_of_speech}\n\n"
                f"Meaning: {meaning}\n\n"
                f"Example: {example}\n\n"
                "ℹ️ This word already exists in your vocabulary."
            )

            await update.message.reply_text(
                message,
                reply_markup=note_keyboard(existing_row_number),
            )
            return

        prompt = f"""
Determine whether the following input is a recognized English word
or phrase.

Input: "{word}"

Rules:
- Accept recognized English words, idioms, and common English phrases.
- Reject non-English words and phrases.
- Reject gibberish, random strings, and profanity or abusive phrases
  that are not meaningful English vocabulary entries.
- If the input is not recognized, set "is_valid" to false.
- Do not invent meanings for invalid inputs.

Return ONLY a valid JSON object with these fields:
{{
    "is_valid": true,
    "word": "The word or phrase",
    "part_of_speech": "Part of speech",
    "meaning": "Simple definition",
    "example": "One natural example sentence"
}}

For invalid inputs, return:
{{
    "is_valid": false,
    "word": "{word}",
    "part_of_speech": "N/A",
    "meaning": "Not a recognized English word or phrase.",
    "example": "N/A"
}}
"""

        response = await client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )

        result = response.choices[0].message.content

        if not result:
            await update.message.reply_text(
                "Sorry, I couldn't find a meaning for that word."
            )
            return

        data = json.loads(result)

        if not data.get("is_valid", False):
            await update.message.reply_text(
                f'❌ "{word}" is not a recognized English word or phrase.\n\n'
                "It hasn't been saved to your vocabulary."
            )
            return

        word = data["word"]
        part_of_speech = data["part_of_speech"]
        meaning = data["meaning"]
        example = data["example"]

        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        worksheet.append_row([
            user_id,
            word,
            part_of_speech,
            meaning,
            example,
            date,
            "",
        ])

        new_row_number = len(worksheet.get_all_values())

        message = (
            f"Word: {word}\n"
            f"Part of Speech: {part_of_speech}\n\n"
            f"Meaning: {meaning}\n\n"
            f"Example: {example}\n\n"
            "✅ Word saved to your vocabulary!"
        )

        await update.message.reply_text(
            message,
            reply_markup=note_keyboard(new_row_number),
        )

    except json.JSONDecodeError:
        print("Groq returned invalid JSON.")
        await update.message.reply_text(
            "Sorry, I couldn't process the meaning. Please try again."
        )

    except Exception as e:
        print("Error:", type(e).__name__, str(e)[:300])
        await update.message.reply_text(
            "Something went wrong while processing your word."
        )


async def getwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    try:
        rows = worksheet.get_all_values()

        if len(rows) <= 1:
            await update.message.reply_text(
                "Your vocabulary is empty. Send me a word to get started!"
            )
            return

        user_words = [
            row for row in rows[1:]
            if row and row[0] == user_id
        ]

        if not user_words:
            await update.message.reply_text(
                "You haven't saved any words yet. Send me a word first!"
            )
            return

        entries = []

        for index, row in enumerate(user_words, start=1):
            word = row[1] if len(row) > 1 else ""
            part_of_speech = row[2] if len(row) > 2 else ""
            meaning = row[3] if len(row) > 3 else ""
            example = row[4] if len(row) > 4 else ""
            note = row[6] if len(row) > 6 else ""

            entry = (
                f"{index}. {word} ({part_of_speech})\n"
                f"Meaning: {meaning}\n"
                f"Example: {example}"
            )

            if note.strip():
                entry += f"\n📝 My Note: {note}"

            entries.append(entry)

        header = f"📚 YOUR VOCABULARY ({len(entries)} words)\n\n"
        separator = "\n\n━━━━━━━━━━━━━━\n\n"
        max_length = 3800

        messages = []
        current_message = header

        for entry in entries:
            addition = entry + separator

            if len(current_message) + len(addition) > max_length:
                messages.append(current_message.rstrip())
                current_message = entry + separator
            else:
                current_message += addition

        if current_message.strip():
            messages.append(current_message.rstrip())

        for message in messages:
            await update.message.reply_text(message)

    except Exception as e:
        print(
            "Error retrieving vocabulary:",
            type(e).__name__,
            str(e)[:300]
        )
        await update.message.reply_text(
            "Something went wrong while retrieving your vocabulary."
        )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getwords", getwords))
    app.add_handler(CommandHandler("cancel", cancel))

    app.add_handler(CallbackQueryHandler(
        add_note_callback,
        pattern=r"^note:\d+$",
    ))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_word,
        )
    )

    print("FetchMeaningBot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
