import asyncio
import datetime
import os
import random
import re

from dotenv import load_dotenv
from pyrogram import Client, filters
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

url_regex = r"((?:https?:\/\/)?(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()!@:%_\+.~#?&\/\/=]*))"
tme_regex = r"(?:https?:\/\/)?t\.me\/([a-zA-Z0-9_]+)\/?(?:\d+)?"


async def parse(channel_id, iteration: int):
    # Delay
    await asyncio.sleep(5 + random.uniform(0, 4))

    # Get Channel Info
    try:
        channel_info = await app.get_chat(channel_id)
    except FloodWait as e:
        print(f"FloodWait(ChannelInfo): {e.value}")
        await asyncio.sleep(e.value + 1)  # Wait "value" seconds before continuing
        channel_info = await app.get_chat(channel_id)

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

    # Check if iteration is greater than threshold
    if iteration > 2:
        return

    # Go through all messages in the channel
    try:
        history = app.get_chat_history(channel_id, limit=2500)
    except FloodWait as e:
        print(f"FloodWait(History): {e.value}")
        await asyncio.sleep(e.value + 1)
        history = app.get_chat_history(channel_id, limit=2500)

    async for message in history:
        print(f"@{channel_info.username}: {message.id}/{message.date}")
        await asyncio.sleep(2 + random.uniform(0, 2))

        # Check if the message is forwarded
        if message.forward_from_chat:
            # Create Relation in MongoDB
            db.relations.insert_one({
                "channel_id": channel_id,
                "message_id": message.id,
                "author_signature": message.author_signature,
                "relation_type": "forward",
                "source": message.forward_from_chat.id,
                "sent_at": message.date,
            })

            # Parse the source channel
            await parse(message.forward_from_chat.id, iteration + 1)
        elif message.entities:  # Check if the message contains URL entities
            for entity in message.entities:
                if entity.type == MessageEntityType.TEXT_LINK:
                    # Check if the URL is a t.me link
                    if re.match(tme_regex, entity.url):
                        # Check if it is a link to the same channel
                        if re.match(tme_regex, entity.url).group(1) == channel_info.username:
                            continue

                        # Create Relation in MongoDB
                        db.relations.insert_one({
                            "channel_id": channel_id,
                            "message_id": message.id,
                            "author_signature": message.author_signature,
                            "relation_type": "tme",
                            "source": re.match(tme_regex, entity.url).group(1),
                            "sent_at": message.date,
                        })

                        # Parse the source channel
                        await parse(re.match(tme_regex, entity.url).group(1), iteration + 1)
                    else:
                        # Create Relation in MongoDB
                        db.relations.insert_one({
                            "channel_id": channel_id,
                            "message_id": message.id,
                            "author_signature": message.author_signature,
                            "relation_type": "url",
                            "source": entity.url,
                            "sent_at": message.date,
                        })
                elif entity.type == MessageEntityType.URL:
                    # Check if URL is t.me link
                    if re.match(tme_regex, message.text[entity.offset:entity.offset + entity.length]):
                        # Check if it is a link to the same channel
                        if re.match(tme_regex, message.text[entity.offset:entity.offset + entity.length]).group(
                                1) == channel_info.username:
                            continue

                        # Create Relation in MongoDB
                        db.relations.insert_one({
                            "channel_id": channel_id,
                            "message_id": message.id,
                            "author_signature": message.author_signature,
                            "relation_type": "tme",
                            "source": re.match(tme_regex,
                                               message.text[entity.offset:entity.offset + entity.length]).group(1),
                            "sent_at": message.date,
                        })

                        # Parse the source channel
                        await parse(
                            re.match(tme_regex, message.text[entity.offset:entity.offset + entity.length]).group(1),
                            iteration + 1)
                    else:
                        # Create Relation in MongoDB
                        db.relations.insert_one({
                            "channel_id": channel_id,
                            "message_id": message.id,
                            "author_signature": message.author_signature,
                            "relation_type": "url",
                            "source": message.text[entity.offset:entity.offset + entity.length],
                            "sent_at": message.date,
                        })


print("Starting parsing", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"))

asyncio.get_event_loop().run_until_complete(parse("cat0news", 0))
