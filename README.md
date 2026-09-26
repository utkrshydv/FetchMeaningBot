# FetchMeaningBot

A Telegram bot that helps you build your English vocabulary by saving words and phrases you come across while watching movies, reading, or going about your day.

## Features

* **Word Meanings:** Get the meaning, part of speech, and an example sentence for any English word or phrase.
* **Vocabulary Collection:** Save words to your personal vocabulary list.
* **Add Notes:** Attach personal notes to saved words.
* **Duplicate Detection:** Retrieve previously saved words without creating duplicate entries.
* **View Your Words:** Use `/getwords` to view your saved vocabulary.

## Tech Stack

* Python
* Telegram Bot API
* Groq API
* Google Sheets

## Setup

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd FetchMeaningBot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
GOOGLE_SHEET_ID=your_google_sheet_id
```

### 4. Configure Google Sheets

Place your Google service account credentials in a file named `credentials.json` in the project root.

Ensure that the Google Sheet is shared with the service account email address.

### 5. Run the Bot

```bash
python bot.py
```

## Usage

1. Start the bot using `/start`.
2. Send an English word or phrase.
3. Get its meaning and an example sentence.
4. Add a personal note if needed.
5. Use `/getwords` to view your saved vocabulary.

---

Built to make learning new words a little easier, one phrase at a time.
