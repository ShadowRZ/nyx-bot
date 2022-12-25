import asyncio
import logging
import os
import re
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from io import BytesIO, StringIO

from nio import AsyncClient, MatrixRoom, RoomMessageText, UploadResponse
from wand.image import Image
from wordcloud import WordCloud

import nyx_bot
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
    sender: str,
):
    bytesio = BytesIO()
    texts = gather_messages(room, sender)
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
        "type": "image",
    }

    await client.room_send(room.room_id, message_type="m.room.message", content=content)


def gather_messages(
    room: MatrixRoom,
    sender: str,
):
    stringio = StringIO()
    msg_items = (
        MatrixMessage.select()
        .where(
            (MatrixMessage.room_id == room.room_id) & (MatrixMessage.sender == sender)
        )
        .order_by(MatrixMessage.origin_server_ts.desc())
    )
    for msg_item in msg_items:
        if msg_item.formatted_body is not None:
            string = re.sub(r"<mx-reply>.*</mx-reply>", "", msg_item.formatted_body)
            print(strip_tags(string), file=stringio)
        elif msg_item.body is not None:
            print(msg_item.body, file=stringio)
        else:
            continue

    ret = stringio.getvalue()
    return ret
