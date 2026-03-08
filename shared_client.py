# Copyright (c) 2026 TeamJB
# Repository: https://github.com/teamjb1/teamjassbeniwal-ctrl
# Licensed under the GNU General Public License v3.0.

from telethon import TelegramClient
from config import API_ID, API_HASH, BOT_TOKEN, STRING
from pyrogram import Client
import sys

client = TelegramClient("teamjbbot", API_ID, API_HASH)
app = Client("pyrogrambot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = Client("4gbbot", api_id=API_ID, api_hash=API_HASH, session_string=STRING)

async def start_client():
    if not client.is_connected():
        await client.start(bot_token=BOT_TOKEN)
        print("TeamJB Library Started...")

    if STRING:
        try:
            await userbot.start()
            print("Userbot started...")
        except Exception as e:
            print(f"Session error: please check your premium string session. {e}")
            sys.exit(1)

    await app.start()
    print("Pyrogram App Started...")
    return client, app, userbot
