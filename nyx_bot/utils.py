import math
from datetime import datetime
from html.parser import HTMLParser
from io import BytesIO, StringIO
from random import Random
from typing import Dict, Optional, Tuple
from urllib.parse import unquote, urlparse
from zlib import crc32

from nio import (
    AsyncClient,
    DownloadError,
    Event,
    MatrixRoom,
    RoomGetEventError,
    RoomMessageText,
)
from wand.image import Image

from nyx_bot.errors import NyxBotRuntimeError
from nyx_bot.parsers import MatrixHTMLParser
from nyx_bot.quote_image import make_quote_image
from nyx_bot.storage import UserTag


def user_name(room: MatrixRoom, user_id: str) -> Optional[str]:
    """Get display name for a user."""
    if user_id not in room.users:
        return None
    user = room.users[user_id]
    return user.name


async def get_body(
    client: AsyncClient, room_id: str, event_id: str, replace_map: Optional[str] = None
) -> str:
    if replace_map is None:
        replace_map = {}
    if event_id not in replace_map:
        target_response = await client.room_get_event(room_id, event_id)
        if isinstance(target_response, RoomGetEventError):
            error = target_response.message
            raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
        target_event = target_response.event
        return target_event.body
    else:
        new_evid = replace_map.get(event_id)
        target_response = await client.room_get_event(room_id, new_evid)
        if isinstance(target_response, RoomGetEventError):
            error = target_response.message
            raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
        target_event = target_response.event
        content = target_event.source.get("content")
        new_content = content.get("m.new_content")
        return new_content.get("body")


async def get_formatted_body(
    client: AsyncClient, room: MatrixRoom, event_id: str, replace_map: Dict[str, str]
) -> Optional[str]:
    if event_id not in replace_map:
        target_response = await client.room_get_event(room.room_id, event_id)
        if isinstance(target_response, RoomGetEventError):
            error = target_response.message
            raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
        target_event = target_response.event
        return target_event.formatted_body
    else:
        new_evid = replace_map.get(event_id)
        target_response = await client.room_get_event(room.room_id, new_evid)
        if isinstance(target_response, RoomGetEventError):
            error = target_response.message
            raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
        target_event = target_response.event
        content = target_event.source.get("content")
        new_content = content.get("m.new_content")
        return new_content.get("formatted_body")


def strip_beginning_quote(original: str) -> str:
    if original.startswith(">"):
        count = 0
        splited = original.splitlines()
        for i in splited:
            if i.startswith(">"):
                count += 1
            elif i == "":
                count += 1
                return "\n".join(splited[count:])

    return original


def get_reply_to(event: Event) -> Optional[str]:
    content = event.source.get("content")
    reply_to = ((content.get("m.relates_to") or {}).get("m.in_reply_to") or {}).get(
        "event_id"
    )
    return reply_to


def is_bot_event(event: Event) -> bool:
    content = event.source.get("content")
    return "io.github.shadowrz.nyx_bot" in content


def get_replaces(event: Event) -> Optional[str]:
    content = event.source.get("content")
    relates_to = content.get("m.relates_to") or {}
    rel_type = relates_to.get("rel_type")
    if rel_type == "m.replace":
        event_id = relates_to.get("event_id")
        return event_id
    return None


def get_external_url(event: Event) -> Optional[str]:
    content = event.source.get("content")
    return content.get("external_url")


def make_datetime(origin_server_ts: int):
    ts = origin_server_ts / 1000
    return datetime.fromtimestamp(ts)


def parse_matrixdotto_link(link: str):
    replaced = link.replace("https://matrix.to/#/", "https://matrix.to/")
    parsed = urlparse(replaced)
    paths = parsed.path.split("/")
    if len(paths) == 1:
        return None
    elif len(paths) == 2:
        identifier = unquote(paths[1])
        type_ = None
        if identifier.startswith("@"):
            # User
            type_ = "user"
        elif identifier.startswith("!"):
            # Room ID
            type_ = "room"
        elif parsed.path == "/":
            # Named Room
            type_ = "room_named"
            identifier = f"#{parsed.fragment}"
        return type_, identifier, None
    elif len(paths) == 3:
        # Must be an event ID
        room = unquote(paths[1])
        event_id = unquote(paths[2])
        return "event", room, event_id


async def make_single_quote_image(
    client: AsyncClient,
    room: MatrixRoom,
    target_event: RoomMessageText,
    replace_map: dict,
    show_user: bool = True,
) -> Image:
    sender = target_event.sender
    body = ""
    formatted = True
    formatted_body = await get_formatted_body(
        client, room, target_event.event_id, replace_map
    )
    if not formatted_body:
        formatted = False
    if formatted:
        parser = MatrixHTMLParser()
        parser.feed(formatted_body)
        body = parser.into_pango_markup()
    else:
        body = await get_body(client, room.room_id, target_event.event_id, replace_map)
        if get_reply_to(target_event):
            body = strip_beginning_quote(body)
        if len(body) > 1000:
            body_stripped = body[:1000]
            body = f"{body_stripped}..."
    sender_name = user_name(room, sender)
    sender_avatar = room.avatar_url(sender)
    image = None
    if show_user:
        if sender_avatar:
            avatar_resp = await client.download(mxc=sender_avatar)
            if isinstance(avatar_resp, DownloadError):
                error = avatar_resp.message
                raise NyxBotRuntimeError(f"Failed to download {sender_avatar}: {error}")
            data = avatar_resp.body
            bytesio = BytesIO(data)
            image = Image(file=bytesio)
        else:
            image = Image(width=64, height=64, background="#FFFF00")
    else:
        sender_name = None
    user_tag = UserTag.get_or_none(
        (UserTag.room_id == room.room_id) & (UserTag.sender == sender)
    )
    tag_name = None
    if user_tag:
        tag_name = f"#{user_tag.tag}"
    quote_image = await make_quote_image(sender_name, body, image, formatted, tag_name)
    return quote_image


def make_divergence(room: MatrixRoom):
    seed = crc32(room.room_id.encode())
    divergence = Random(seed)
    first_value = divergence.gammavariate(1, 0.5)
    if first_value >= 2:
        result = first_value * divergence.random()
        if result < 0.000001:
            result = divergence.random() + first_value / 10
    else:
        result = first_value

    return result


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


async def parse_wordcloud_args(
    args,
    client: AsyncClient,
    room: MatrixRoom,
    event: RoomMessageText,
    reply_to: Optional[str],
) -> Tuple[Optional[str], Optional[int]]:
    sender = None
    days = None
    if not reply_to:
        sender = event.sender
    else:
        target_event = await client.room_get_event(room.room_id, reply_to)
        if isinstance(target_event, RoomGetEventError):
            error = target_event.message
            raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
        sender = target_event.event.sender
    if args:
        if args[0] == "all":
            sender = None
        else:
            try:
                days = float(args[0])
                if math.isnan(days) or math.isinf(days):
                    raise ValueError
            except ValueError:
                raise NyxBotRuntimeError("The day argument given is not vaild.")
            else:
                if (len(args) >= 2) and (args[1] == "all"):
                    sender = None
                else:
                    raise NyxBotRuntimeError("Argument is not valid.")

    return sender, days


def should_record_message_content(room_features, room_id: str) -> bool:
    return room_features[room_id]["record_messages"]


def should_enable_jerryxiao(room_features, room_id: str) -> bool:
    return room_features[room_id]["jerryxiao"]


def should_enable_randomdraw(room_features, room_id: str) -> bool:
    return room_features[room_id]["randomdraw"]
