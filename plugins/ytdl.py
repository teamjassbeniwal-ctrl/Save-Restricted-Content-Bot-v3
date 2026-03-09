# ---------------------------------------------------
# File Name: ytdl.py (fixed version)
# Description: Telegram downloader bot module
# ---------------------------------------------------

import yt_dlp
import os
import tempfile
import time
import asyncio
import random
import string
import requests
import logging
import math
import aiohttp
import aiofiles

from concurrent.futures import ThreadPoolExecutor
from shared_client import client, app
from telethon import events
from telethon.tl.types import DocumentAttributeVideo

from utils.func import get_video_metadata, screenshot
from devgagantools import fast_upload

from config import YT_COOKIES, INSTA_COOKIES

from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC
from mutagen.mp3 import MP3


logger = logging.getLogger(__name__)

thread_pool = ThreadPoolExecutor()
ongoing_downloads = {}
user_progress = {}

# ---------------------------------------------------
# Utility functions
# ---------------------------------------------------

def get_random_string(length=7):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def d_thumbnail(url, path):
    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return path
    except Exception as e:
        logger.error(f"Thumbnail download error: {e}")
        return None


async def download_thumbnail_async(url, path):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            if r.status == 200:
                with open(path, "wb") as f:
                    f.write(await r.read())


async def extract_audio_async(opts, url):
    def run():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, run)


# ---------------------------------------------------
# AUDIO DOWNLOAD
# ---------------------------------------------------

async def process_audio(client, event, url, cookies_env_var=None):

    cookies = None

    if cookies_env_var == "YT_COOKIES":
        cookies = YT_COOKIES
    elif cookies_env_var == "INSTA_COOKIES":
        cookies = INSTA_COOKIES

    temp_cookie_path = None

    if cookies:
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
            f.write(cookies)
            temp_cookie_path = f.name

    filename = f"@team_spy_pro_{event.sender_id}.mp3"

    opts = {
        "outtmpl": filename,
        "format": "bestaudio/best",
        "cookiefile": temp_cookie_path,
        "quiet": True
    }

    msg = await event.reply("**Starting audio extraction...**")

    try:

        info = await extract_audio_async(opts, url)
        title = info.get("title", "Audio")

        await msg.edit("**Editing metadata...**")

        if os.path.exists(filename):

            def edit():

                audio = MP3(filename, ID3=ID3)

                try:
                    audio.add_tags()
                except:
                    pass

                audio.tags["TIT2"] = TIT2(encoding=3, text=title)
                audio.tags["TPE1"] = TPE1(encoding=3, text="Team SPY")

                audio.save()

            await asyncio.to_thread(edit)

        await msg.delete()

        prog = await client.send_message(event.chat_id, "**Uploading...**")

        uploaded = await fast_upload(
            client,
            filename,
            reply=prog,
            progress_bar_function=lambda d, t: progress_callback(d, t, event.chat_id)
        )

        await client.send_file(
            event.chat_id,
            uploaded,
            caption=f"**{title}**"
        )

        await prog.delete()

    except Exception as e:
        await event.reply(f"Error: `{e}`")

    finally:

        if os.path.exists(filename):
            os.remove(filename)

        if temp_cookie_path and os.path.exists(temp_cookie_path):
            os.remove(temp_cookie_path)


# ---------------------------------------------------
# VIDEO DOWNLOAD
# ---------------------------------------------------

async def process_video(client, event, url, cookies_env_var=None, check_duration_and_size=False):

    logger.info(f"Downloading {url}")

    cookies = None

    if cookies_env_var == "YT_COOKIES":
        cookies = YT_COOKIES
    elif cookies_env_var == "INSTA_COOKIES":
        cookies = INSTA_COOKIES

    filename = get_random_string() + ".mp4"
    path = os.path.abspath(filename)

    temp_cookie = None

    if cookies:
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
            f.write(cookies)
            temp_cookie = f.name

    opts = {
        "outtmpl": path,
        "format": "best",
        "cookiefile": temp_cookie
    }

    msg = await event.reply("**Downloading video...**")

    try:

        def run():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=True)

        info = await asyncio.get_event_loop().run_in_executor(thread_pool, run)

        title = info.get("title", "Video")

        meta = await get_video_metadata(path)

        thumb = await screenshot(path, meta["duration"], event.sender_id)

        await msg.delete()

        prog = await client.send_message(event.chat_id, "**Uploading...**")

        uploaded = await fast_upload(
            client,
            path,
            reply=prog,
            progress_bar_function=lambda d, t: progress_callback(d, t, event.chat_id)
        )

        await client.send_file(
            event.chat_id,
            uploaded,
            caption=title,
            attributes=[
                DocumentAttributeVideo(
                    duration=meta["duration"],
                    w=meta["width"],
                    h=meta["height"],
                    supports_streaming=True
                )
            ],
            thumb=thumb
        )

        await prog.delete()

    except Exception as e:
        await event.reply(f"Error: `{e}`")

    finally:

        if os.path.exists(path):
            os.remove(path)

        if temp_cookie and os.path.exists(temp_cookie):
            os.remove(temp_cookie)


# ---------------------------------------------------
# COMMANDS
# ---------------------------------------------------

@client.on(events.NewMessage(pattern="/dl"))
async def download_video_cmd(event):

    if len(event.text.split()) < 2:
        return await event.reply("Usage: `/dl link`")

    url = event.text.split()[1]

    await process_video(client, event, url)


@client.on(events.NewMessage(pattern="/adl"))
async def download_audio_cmd(event):

    if len(event.text.split()) < 2:
        return await event.reply("Usage: `/adl link`")

    url = event.text.split()[1]

    await process_audio(client, event, url)


# ---------------------------------------------------
# PROGRESS
# ---------------------------------------------------

def progress_callback(done, total, user):

    percent = done * 100 / total

    done_mb = done / (1024 * 1024)
    total_mb = total / (1024 * 1024)

    bar = "♦" * int(percent / 10) + "◇" * (10 - int(percent / 10))

    return (
        f"Uploading...\n"
        f"{bar}\n"
        f"{percent:.2f}%\n"
        f"{done_mb:.2f}MB / {total_mb:.2f}MB"
    )


# ---------------------------------------------------
# TIME UTILS
# ---------------------------------------------------

def convert(seconds: int):

    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{hours:02}:{minutes:02}:{seconds:02}"
