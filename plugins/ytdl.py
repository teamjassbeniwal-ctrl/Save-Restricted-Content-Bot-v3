# ---------------------------------------------------
# File Name: ytdl.py
# Description: Pyrogram/Telethon bot for downloading YouTube/Instagram videos and audio
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Telegram: https://t.me/team_spy_pro
# YouTube: https://youtube.com/@dev_gagan
# Version: 2.0.6 (corrected)
# License: MIT License
# ---------------------------------------------------

import os
import time
import asyncio
import tempfile
import random
import string
import logging
import math
import requests
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import aiofiles
import yt_dlp
from telethon import events
from telethon.tl.types import DocumentAttributeVideo
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC

from shared_client import client, app
from config import YT_COOKIES, INSTA_COOKIES
from utils.func import get_video_metadata, screenshot
from devgagantools import fast_upload

logger = logging.getLogger(__name__)

thread_pool = ThreadPoolExecutor()
ongoing_downloads = {}
user_progress = {}


def get_random_string(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def d_thumbnail(thumbnail_url, save_path):
    try:
        response = requests.get(thumbnail_url, stream=True)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)
        return save_path
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download thumbnail: {e}")
        return None


async def download_thumbnail_async(url, path):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                with open(path, 'wb') as f:
                    f.write(await response.read())


async def extract_audio_async(ydl_opts, url):
    def sync_extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)
    return await asyncio.get_event_loop().run_in_executor(thread_pool, sync_extract)


async def process_audio(client, event, url, cookies_env_var=None):
    cookies = cookies_env_var

    temp_cookie_path = None
    if cookies:
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_cookie_file:
            temp_cookie_file.write(cookies)
            temp_cookie_path = temp_cookie_file.name

    random_filename = f"@team_spy_pro_{event.sender_id}"
    download_path = f"{random_filename}.mp3"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f"{random_filename}.%(ext)s",
        'cookiefile': temp_cookie_path if temp_cookie_path else None,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'quiet': True,
        'noplaylist': True,
    }

    progress_message = await event.reply("**__Starting audio extraction...__**")

    try:
        info_dict = await extract_audio_async(ydl_opts, url)
        title = info_dict.get('title', 'Extracted Audio')

        await progress_message.edit("**__Editing metadata...__**")

        if os.path.exists(download_path):
            async def edit_metadata():
                audio_file = MP3(download_path, ID3=ID3)
                try:
                    audio_file.add_tags()
                except Exception:
                    pass
                audio_file.tags["TIT2"] = TIT2(encoding=3, text=title)
                audio_file.tags["TPE1"] = TPE1(encoding=3, text="Team SPY")
                audio_file.tags["COMM"] = COMM(encoding=3, lang="eng", desc="Comment", text="Processed by Team SPY")

                thumbnail_url = info_dict.get('thumbnail')
                if thumbnail_url:
                    thumbnail_path = os.path.join(tempfile.gettempdir(), "thumb.jpg")
                    await download_thumbnail_async(thumbnail_url, thumbnail_path)
                    with open(thumbnail_path, 'rb') as img:
                        audio_file.tags["APIC"] = APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=img.read())
                    os.remove(thumbnail_path)
                audio_file.save()

            await edit_metadata()

        chat_id = event.chat_id
        if os.path.exists(download_path):
            await progress_message.delete()
            prog = await client.send_message(chat_id, "**__Starting Upload...__**")
            uploaded = await fast_upload(client, download_path, reply=prog,
                                         progress_bar_function=lambda done, total: progress_callback(done, total, chat_id))
            await client.send_file(chat_id, uploaded, caption=f"**{title}**\n\n**__Powered by Team SPY__**")
            await prog.delete()
        else:
            await event.reply("**__Audio file not found after extraction!__**")

    except Exception as e:
        logger.exception("Error during audio extraction or upload")
        await event.reply(f"**__An error occurred: {e}__**")
    finally:
        if os.path.exists(download_path):
            os.remove(download_path)
        if temp_cookie_path and os.path.exists(temp_cookie_path):
            os.remove(temp_cookie_path)


@client.on(events.NewMessage(pattern="/adl"))
async def adl_handler(event):
    user_id = event.sender_id
    if user_id in ongoing_downloads:
        await event.reply("**You already have an ongoing download. Please wait!**")
        return

    if len(event.message.text.split()) < 2:
        await event.reply("**Usage:** `/adl <video-link>`")
        return

    url = event.message.text.split()[1]
    ongoing_downloads[user_id] = True

    try:
        if "instagram.com" in url:
            await process_audio(client, event, url, cookies_env_var=INSTA_COOKIES)
        elif "youtube.com" in url or "youtu.be" in url:
            await process_audio(client, event, url, cookies_env_var=YT_COOKIES)
        else:
            await process_audio(client, event, url)
    finally:
        ongoing_downloads.pop(user_id, None)


# ---------------- Video Section ----------------

async def fetch_video_info(url, ydl_opts, progress_message, check_duration_and_size):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)

        if check_duration_and_size:
            duration = info_dict.get('duration', 0)
            if duration and duration > 3 * 3600:
                await progress_message.edit("**❌ Video longer than 3 hours. Aborted!**")
                return None

            size = info_dict.get('filesize_approx', 0)
            if size and size > 2 * 1024 * 1024 * 1024:
                await progress_message.edit("**❌ Video size larger than 2GB. Aborted!**")
                return None

        return info_dict


def download_video(url, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


async def process_video(client, event, url, cookies_env_var=None, check_duration_and_size=False):
    cookies = cookies_env_var
    random_filename = get_random_string() + ".mp4"
    download_path = os.path.abspath(random_filename)
    temp_cookie_path = None
    if cookies:
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_cookie_file:
            temp_cookie_file.write(cookies)
            temp_cookie_path = temp_cookie_file.name

    ydl_opts = {
        'outtmpl': download_path,
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'cookiefile': temp_cookie_path if temp_cookie_path else None,
        'writethumbnail': True,
        'quiet': True,
    }

    progress_message = await event.reply("**__Starting download...__**")
    try:
        info_dict = await fetch_video_info(url, ydl_opts, progress_message, check_duration_and_size)
        if not info_dict:
            return

        await asyncio.to_thread(download_video, url, ydl_opts)
        title = info_dict.get('title', 'Powered by Team SPY')
        k = await get_video_metadata(download_path)
        metadata = {'width': k['width'], 'height': k['height'], 'duration': k['duration']}

        thumbnail_file = None
        if info_dict.get('thumbnail'):
            thumbnail_file = os.path.join(tempfile.gettempdir(), get_random_string() + ".jpg")
            d_thumbnail(info_dict['thumbnail'], thumbnail_file)

        await progress_message.delete()
        prog = await client.send_message(event.chat_id, "**__Starting Upload...__**")
        uploaded = await fast_upload(client, download_path, reply=prog,
                                     progress_bar_function=lambda d, t: progress_callback(d, t, event.chat_id))
        await client.send_file(event.chat_id, uploaded, caption=f"**{title}**",
                               attributes=[DocumentAttributeVideo(duration=metadata['duration'],
                                                                 w=metadata['width'], h=metadata['height'],
                                                                 supports_streaming=True)],
                               thumb=thumbnail_file if thumbnail_file else None)
        await prog.delete()
    finally:
        if os.path.exists(download_path):
            os.remove(download_path)
        if temp_cookie_path and os.path.exists(temp_cookie_path):
            os.remove(temp_cookie_path)
        if thumbnail_file and os.path.exists(thumbnail_file):
            os.remove(thumbnail_file)


@client.on(events.NewMessage(pattern="/dl"))
async def dl_handler(event):
    user_id = event.sender_id
    if user_id in ongoing_downloads:
        await event.reply("**You already have an ongoing download. Please wait!**")
        return

    if len(event.message.text.split()) < 2:
        await event.reply("**Usage:** `/dl <video-link>`")
        return

    url = event.message.text.split()[1]
    ongoing_downloads[user_id] = True

    try:
        if "instagram.com" in url:
            await process_video(client, event, url, INSTA_COOKIES)
        elif "youtube.com" in url or "youtu.be" in url:
            await process_video(client, event, url, YT_COOKIES, check_duration_and_size=True)
        else:
            await process_video(client, event, url)
    finally:
        ongoing_downloads.pop(user_id, None)


# ---------------- Progress Callback ----------------

def progress_callback(done, total, user_id):
    if user_id not in user_progress:
        user_progress[user_id] = {'previous_done': 0, 'previous_time': time.time()}

    user_data = user_progress[user_id]
    percent = (done / total) * 100
    completed_blocks = int(percent // 10)
    progress_bar = "♦" * completed_blocks + "◇" * (10 - completed_blocks)

    done_mb = done / (1024 * 1024)
    total_mb = total / (1024 * 1024)

    speed = done - user_data['previous_done']
    elapsed_time = time.time() - user_data['previous_time']
    speed_bps = speed / elapsed_time if elapsed_time else 0
    speed_mbps = (speed_bps * 8) / (1024 * 1024) if speed_bps else 0
    remaining_time = (total - done) / speed_bps if speed_bps else 0

    user_data['previous_done'] = done
    user_data['previous_time'] = time.time()

    final = (
        f"╭──────────────────╮\n"
        f"│        **__Uploading...__**       \n"
        f"├──────────\n"
        f"│ {progress_bar}\n\n"
        f"│ **__Progress:__** {percent:.2f}%\n"
        f"│ **__Done:__** {done_mb:.2f} MB / {total_mb:.2f} MB\n"
        f"│ **__Speed:__** {speed_mbps:.2f} Mbps\n"
        f"│ **__Time Remaining:__** {remaining_time/60:.2f} min\n"
        f"╰──────────────────╯\n\n"
        f"**__Powered by Team SPY__**"
    )
    return final
