import asyncio
import datetime
import os
import random
import re

import pyrogram.types
from dotenv import load_dotenv
from pyrogram import Client
from pymongo import MongoClient
from pyrogram.enums import MessageEntityType
from pyrogram.errors import FloodWait

load_dotenv()

# MongoDB connection
print("Connecting to MongoDB")
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["telegram-graph"]

# Pyrogram client
print("Creating Pyrogram client")
app = Client("my_account", api_id=os.getenv("API_ID"), api_hash=os.getenv("API_HASH"))

print("Connecting to Telegram")
app.start()

url_regex = r"((?:https?:\/\/)?(?:www\.)?([-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6})\b(?:[-a-zA-Z0-9()!@:%_\+.~#?&\/\/=]*))"
tme_regex = r"(?:https?:\/\/)?t\.me\/([a-zA-Z0-9_]+)\/?(?:\d+)?"

starting_channel = "cat0news"
message_limit = 2500
iteration_limit = 1


async def parse(channel_id, title, iteration: int):
    # Delay
    await asyncio.sleep(3 + random.uniform(0, 3))

    # Get Channel Info
    try:
        channel_info = await app.get_chat(channel_id)
    except FloodWait as e:
        # FloodWait sleep
        print(f"FloodWait(ChannelInfo): {e.value}")
        await asyncio.sleep(e.value + 1)  # Wait "value" seconds before continuing

        # Retry
        try:
            channel_info = await app.get_chat(channel_id)
        except Exception as e:
            print(f"Error(ChannelInfo): {e}")
            return
    except Exception as e:  # For example, if the channel is private
        print(f"Error(ChannelInfo): {e}")

        # Check if the channel is already in the database
        if db.channels.find_one({"id": channel_id}):
            return

        # Create Channel entry in MongoDB
        db.channels.insert_one({
            "id": channel_id,
            "title": title,
            "username": None,
            "member_count": 0,
        })
        return

    # Check if the channel is already in the database
    if db.channels.find_one({"id": channel_info.id}):
        return

    # Create Channel entry in MongoDB
    db.channels.insert_one({
        "id": channel_info.id,
        "title": channel_info.title,
        "username": channel_info.username,
        "member_count": channel_info.members_count,
    })

    # Check if iteration is greater than the limit
    if iteration > iteration_limit:
        return

    # Go through all messages in the channel
    try:
        history = app.get_chat_history(channel_id, limit=message_limit)
    except FloodWait as e:
        # FloodWait sleep
        print(f"FloodWait(History): {e.value}")
        await asyncio.sleep(e.value + 1)

        # Retry
        try:
            history = app.get_chat_history(channel_id, limit=message_limit)
        except Exception as e:
            print(f"Error(History): {e}")
            return
    except Exception as e:
        print(f"Error(History): {e}")
        return

    async for message in history:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"),
              f" @{channel_info.username}: {message.id}/{message.date}")
        await asyncio.sleep(2 + random.uniform(0, 1))

        # Check if the message is forwarded
        if message.forward_from_chat:
            # Create Relation in MongoDB
            db.relations.insert_one({
                "channel_id": channel_info.id,
                "message_id": message.id,
                "author_signature": message.author_signature,
                "relation_type": "forward",
                "source": message.forward_from_chat.id,
                "sent_at": message.date,
            })

            # Parse the source channel
            await parse(message.forward_from_chat.id, message.forward_from_chat.title, iteration + 1)
        elif message.entities:  # Check if the message contains URL entities
            for entity in message.entities:
                if entity.type == MessageEntityType.TEXT_LINK:
                    url = entity.url
                    await parse_url(url, message, iteration)
                elif entity.type == MessageEntityType.URL:
                    url = message.text[entity.offset:entity.offset + entity.length]
                    await parse_url(url, message, iteration)


async def parse_url(url: str, message: pyrogram.types.Message, iteration: int):
    # Check if the URL is a t.me link
    if re.match(tme_regex, url):
        channel_username = re.match(tme_regex, url).group(1)

        # Check if it is a link to the same channel
        if channel_username == message.chat.username:
            return

        # Get Channel Info
        try:
            channel_info = await app.get_chat(channel_username)
        except FloodWait as e:
            # FloodWait sleep
            print(f"FloodWait(ChannelInfo): {e.value}")
            await asyncio.sleep(e.value + 1)  # Wait "value" seconds before continuing

            # Retry
            try:
                channel_info = await app.get_chat(channel_username)
            except Exception as e:
                print(f"Error(ChannelInfo): {e}")
                return
        except Exception as e:  # For example, if the channel is private
            print(f"Error(ChannelInfo): {e}")

            # Create Relation in MongoDB
            db.relations.insert_one({
                "channel_id": message.chat.id,
                "message_id": message.id,
                "author_signature": message.author_signature,
                "relation_type": "tme",
                "source": channel_username,
                "sent_at": datetime.datetime.now(),
            })

            # Check if the channel is already in the database
            if db.channels.find_one({"id": channel_username}):
                return

            # Create Channel entry in MongoDB
            db.channels.insert_one({
                "id": channel_username,
                "title": None,
                "username": None,
                "member_count": 0,
            })

            return

        # Create Relation in MongoDB
        db.relations.insert_one({
            "channel_id": message.chat.id,
            "message_id": message.id,
            "author_signature": message.author_signature,
            "relation_type": "tme",
            "source": channel_info.id,
            "sent_at": datetime.datetime.now(),
        })

        # Parse the source channel
        await parse(channel_info.id, "", iteration + 1)
    elif re.match(url_regex, url):
        # Create Relation in MongoDB
        db.relations.insert_one({
            "channel_id": message.chat.id,
            "message_id": message.id,
            "author_signature": message.author_signature,
            "relation_type": "url",
            "source": re.match(url_regex, url).group(2),
            "sent_at": message.date,
        })


print("Starting parsing", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"))

asyncio.get_event_loop().run_until_complete(parse(starting_channel, "", 0))
