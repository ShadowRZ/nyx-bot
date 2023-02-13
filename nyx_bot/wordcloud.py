import asyncio
import logging
import os
import re
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from typing import Optional, Set, Tuple

from nio import AsyncClient, MatrixRoom, RoomMessageText, UploadResponse
from wand.image import Image
from wordcloud import WordCloud

import nyx_bot
from nyx_bot.chat_functions import send_text_to_room
from nyx_bot.storage import MatrixMessage
from nyx_bot.utils import strip_tags

CUTWORDS_EXE = "nyx_bot-cutword"
FONT = os.path.join(nyx_bot.__path__[0], "wordcloud_font.ttf")
logger = logging.getLogger(__name__)


async def get_word_freqs(text):
    proc = await create_subprocess_exec(
        CUTWORDS_EXE,
        stdin=PIPE,
        stdout=PIPE,
    )

    stdout, _ = await proc.communicate(input=text.encode("utf-8"))

    freqs = {}
    lines = stdout.decode().splitlines()
    for line in lines:
        word, freq = line.split(None, 1)
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
    bytesio = BytesIO()
    start_date = datetime.now()
    end_date = None
    if days is not None:
        end_date = start_date - timedelta(days=days)
    (texts, count, users) = gather_messages(room, sender, end_date)
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
    freqs = await get_word_freqs(texts)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, make_image, freqs, bytesio)

    length = bytesio.getbuffer().nbytes
    bytesio.seek(0)

    image = Image(file=bytesio)
    (width, height) = (image.width, image.height)

    # Seek again
    bytesio.seek(0)
    resp, maybe_keys = await client.upload(
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
        "contained_senders": list(users),
    }

    await client.room_send(room.room_id, message_type="m.room.message", content=content)


DROP_USERS = {"@telegram_1454289754:nichi.co", "@matterbridge:nichi.co"}


def gather_messages(
    room: MatrixRoom,
    sender: Optional[str],
    end_date: Optional[datetime],
) -> Tuple[str, int, Set[str]]:
    stringio = StringIO()
    count = 0
    if sender is None:
        msg_items = (
            MatrixMessage.select()
            .where(MatrixMessage.room_id == room.room_id)
            .order_by(MatrixMessage.origin_server_ts.desc())
        )
    else:
        msg_items = (
            MatrixMessage.select()
            .where(
                (MatrixMessage.room_id == room.room_id)
                & (MatrixMessage.sender == sender)
            )
            .order_by(MatrixMessage.origin_server_ts.desc())
        )
    users = set()
    for msg_item in msg_items:
        if end_date is not None:
            if msg_item.datetime < end_date:
                break
        if msg_item.sender in DROP_USERS:  # XXX: Special case for Arch Linux CN
            continue
        if msg_item.formatted_body is not None:
            string = re.sub(r"<mx-reply>.*</mx-reply>", "", msg_item.formatted_body)
            fwd_match = re.match(
                r"Forwarded message from .*<tg-forward>(.*)</tg-forward>",
                string,
            )
            if fwd_match is not None:
                string = fwd_match.group(1)
            print(strip_tags(string), file=stringio)
        elif msg_item.body is not None:
            # XXX: Special case for Arch Linux CN
            if msg_item.sender == "@matterbridge:nichi.co":
                data = re.sub(r"^\[.*\] ", "", msg_item.body)
                print(data.strip(), file=stringio)
            else:
                print(msg_item.body, file=stringio)
        else:
            continue

        count += 1
        users.add(msg_item.sender)

    ret = stringio.getvalue()
    return (ret, count, users)
