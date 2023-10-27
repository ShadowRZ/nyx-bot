import asyncio
import logging
import os
import re
import time
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from typing import Optional

from nio import AsyncClient, MatrixRoom, RoomMessageText, UploadResponse
from wand.image import Image
from wordcloud import WordCloud

import nyx_bot
from nyx_bot.chat_functions import send_text_to_room
from nyx_bot.storage import MatrixMessage
from nyx_bot.utils import strip_tags

CUTWORDS_EXE = "nyx_bot-cutword"
FONT = os.path.join(nyx_bot.__path__[0], "wordcloud_font.ttf")
TIMEZONE = timezone(timedelta(hours=8))  # UTC+8
logger = logging.getLogger(__name__)


async def get_word_freqs(texts):
    proc = await create_subprocess_exec(
        CUTWORDS_EXE,
        stdin=PIPE,
        stdout=PIPE,
    )

    stringio = StringIO()

    for i in texts:
        print(i, file=stringio)

    stdout, _ = await proc.communicate(input=stringio.getvalue().encode("utf-8"))

    freqs = {}
    lines = stdout.decode().splitlines()
    for line in lines:
        word, freq = line.split(None, 1)
        if len(word) == 1 and word.isascii():
            continue
        else:
            freqs[word] = int(freq)

    return freqs


def make_image(freqs, bytesio):
    image = (
        WordCloud(
            font_path=FONT,
            width=800,
            height=400,
        )
        .generate_from_frequencies(freqs)
        .to_image()
    )
    image.save(bytesio, "PNG")


async def send_wordcloud(
    client: AsyncClient,
    room: MatrixRoom,
    event: RoomMessageText,
    sender: Optional[str],
    days: Optional[int],
):
    st = datetime.now().astimezone(TIMEZONE)
    logger.info(
        f"Starting wordcloud formatting at {st.strftime('%Y-%m-%d %H:%M:%S%z')}"
    )
    st2 = time.time()
    bytesio = BytesIO()
    start_date = datetime.now()
    end_date = None
    if days is not None:
        end_date = start_date - timedelta(days=days)
    texts = MessageIter(room, event.server_timestamp, sender, end_date)

    freqs = await get_word_freqs(texts)
    st3 = time.time()
    logger.info("Analyzed message using %.3f seconds", st3 - st2)

    count = texts.count
    if count == 0:
        await send_text_to_room(
            client,
            room.room_id,
            "No message was found.",
            notice=False,
            markdown_convert=False,
            reply_to_event_id=event.event_id,
            literal_text=True,
        )
        return

    users = len(texts.users)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, make_image, freqs, bytesio)

    st4 = time.time()
    logger.info("Created picture using %.3f seconds", st4 - st3)

    length = bytesio.getbuffer().nbytes
    bytesio.seek(0)

    image = Image(file=bytesio)
    (width, height) = (image.width, image.height)

    # Seek again
    bytesio.seek(0)
    resp, _ = await client.upload(
        bytesio,
        content_type="image/png",
        filename="image.png",
        filesize=length,
    )
    if isinstance(resp, UploadResponse):
        print("Image was uploaded successfully to server. ")
    else:
        print(f"Failed to upload image. Failure response: {resp}")

    content = {
        "body": "[Wordcloud]",
        "info": {
            "size": length,
            "mimetype": "image/png",
            "thumbnail_info": {
                "mimetype": "image/png",
                "size": length,
                "w": width,  # width in pixel
                "h": height,  # height in pixel
            },
            "w": width,  # width in pixel
            "h": height,  # height in pixel
            "thumbnail_url": resp.content_uri,
        },
        "msgtype": "m.image",
        "url": resp.content_uri,
    }

    content["m.relates_to"] = {"m.in_reply_to": {"event_id": event.event_id}}

    # Add custom data for tracking bot message.
    content["io.github.shadowrz.nyx_bot"] = {
        "in_reply_to": event.event_id,
        "type": "wordcloud",
        "state_key": sender,
        "count": count,
        "start_date": start_date.isoformat(sep=" "),
        "end_date": end_date.isoformat(sep=" ") if end_date is not None else None,
        "sender_count": users,
    }

    await client.room_send(room.room_id, message_type="m.room.message", content=content)
    st5 = time.time()
    logger.info("Sending message using %.3f seconds, done.", st5 - st4)


DROP_USERS = {"@telegram_1454289754:nichi.co", "@variation:matrix.org", "@bot:bgme.me"}


class MessageIter:
    LIMIT = 1000

    def __init__(
        self,
        room: MatrixRoom,
        base_ts: int,
        sender: Optional[str],
        end_date: Optional[datetime],
    ):
        self.done = False
        self.sender = sender
        self.end_date = end_date
        self.room = room
        self.users = set()
        self.count = 0
        self.last_ts = base_ts

    def batches(self, limit: int):
        """Return a iterator for query pagination."""
        while not self.done:
            msg_items = MatrixMessage.select().where(
                (MatrixMessage.room_id == self.room.room_id)
                & (MatrixMessage.origin_server_ts < self.last_ts)
            )
            if self.sender is not None:
                msg_items = msg_items.where(MatrixMessage.sender == self.sender)
            if self.end_date is not None:
                msg_items = msg_items.where(MatrixMessage.datetime >= self.end_date)
            msg_items = msg_items.order_by(MatrixMessage.origin_server_ts.desc()).limit(
                limit
            )
            count = msg_items.count()
            if count == 0:
                return
            elif count < limit:
                self.done = True
            yield msg_items

    def __iter__(self):
        for msg_items in self.batches(self.LIMIT):
            for msg_item in msg_items:
                if msg_item.sender in DROP_USERS:  # XXX: Special case for Arch Linux CN
                    continue
                self.count += 1
                string = process_message(msg_item)
                self.users.add(msg_item.sender)
                self.last_ts = msg_item.origin_server_ts
                yield string


def process_message(msg_item):
    if msg_item.formatted_body is not None:
        string = re.sub(r"<mx-reply>.*</mx-reply>", "", msg_item.formatted_body)
        fwd_match = re.match(
            r"Forwarded message from .*<tg-forward>(.*)</tg-forward>",
            string,
        )
        if fwd_match is not None:
            string = fwd_match.group(1)
        return strip_tags(string)
    elif msg_item.body is not None:
        # XXX: Special case for Arch Linux CN
        if msg_item.sender == "@matterbridge:nichi.co":
            data = re.sub(r"^\[.*\] ", "", msg_item.body)
            return data.strip()
        else:
            return msg_item.body
