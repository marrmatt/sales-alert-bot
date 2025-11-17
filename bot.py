from dotenv import load_dotenv
load_dotenv()                     # ← This reads your .env file automatically

import os
import json
import time
import threading
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------- Config (threshold & chat_id) ----------
CONFIG_FILE = 'config.json'
try:
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    config = {'threshold': 0, 'chat_id': None}
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

# ---------- Telegram Bot ----------
bot = telebot.TeleBot(os.environ['BOT_TOKEN'])

@bot.message_handler(commands=['start'])
def start(message):
    config['chat_id'] = message.chat.id
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
    bot.reply_to(message, "You're now registered for alerts! Use /set_threshold <number> to set your quantity threshold (default is 0 = all sales).")

@bot.message_handler(commands=['set_threshold'])
def set_threshold(message):
    try:
        thresh = int(message.text.split()[1])
        config['threshold'] = thresh
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        bot.reply_to(message, f"Threshold set to {thresh}. Alerts only for quantity > {thresh}.")
    except (IndexError, ValueError):
        bot.reply_to(message, "Usage: /set_threshold <number>   (example: /set_threshold 10)")

# ---------- Google Sheets ----------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', scope)
client = gspread.authorize(creds)

# ← THIS LINE IS NOW CORRECT
sheet = client.open_by_url(os.environ['SHEET_URL']).sheet1   # change .sheet1 → .worksheet("Your Tab Name") if needed

# ---------- Monitoring new rows ----------
def monitor_sheet():
    all_values = sheet.get_all_values()
    last_row_count = len(all_values)  # Start from current row count

    print(f"Monitoring started. Initial row count: {last_row_count}")

    while True:
        time.sleep(10)
        all_values = sheet.get_all_values()
        current_row_count = len(all_values)

        print(f"Checking rows... Last: {last_row_count}, Current: {current_row_count}")

        if current_row_count > last_row_count:
            for i in range(last_row_count + 1, current_row_count + 1):
                row = all_values[i - 1]  # Adjust for 0-based index
                print("New row detected:", row)

                if len(row) >= 3 and row[0].strip():
                    product = row[0].strip()
                    try:
                        quantity = int(row[1].strip())
                    except (ValueError, IndexError):
                        print("Skipping row due to invalid quantity:", row)
                        continue
                    customer = row[2].strip()

                    if quantity > config['threshold'] and config['chat_id']:
                        msg = f"New sale!\nProduct: {product}\nQuantity: {quantity}\nCustomer: {customer}"
                        bot.send_message(config['chat_id'], msg)
                        print("Alert sent:", msg)
                    else:
                        print("Row skipped due to threshold or missing chat_id.")

            last_row_count = current_row_count

# ---------- Start everything ----------
monitor_thread = threading.Thread(target=monitor_sheet)
monitor_thread.daemon = True
monitor_thread.start()

print("Bot is running... Waiting for new sales!")
bot.polling(none_stop=True)