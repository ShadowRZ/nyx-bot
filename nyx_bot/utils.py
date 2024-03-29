import math
import re
from datetime import datetime
from html.parser import HTMLParser
from io import StringIO
from random import Random
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import xxhash
from nio import AsyncClient, Event, MatrixRoom, RoomGetEventError, RoomMessageText

from nyx_bot.errors import NyxBotRuntimeError


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
    reply_to = content.get("m.relates_to", {}).get("m.in_reply_to", {}).get("event_id")
    return reply_to


def get_bot_event_type(event: Event) -> Optional[str]:
    if is_bot_event(event):
        content = event.source.get("content")
        type = content.get("io.github.shadowrz.nyx_bot", {}).get("type")
        return type
    else:
        return None


def is_bot_event(event: Event) -> bool:
    content = event.source.get("content")
    return "io.github.shadowrz.nyx_bot" in content


def get_replaces(event: Event) -> Optional[str]:
    content = event.source.get("content")
    relates_to = content.get("m.relates_to", {})
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


def tg_link_to_tdotme_link(tg_link: str):
    parsed = urlparse(tg_link)
    qs_parsed = parse_qs(parsed.query)
    domain = qs_parsed["domain"][0]
    post_id = qs_parsed["post"][0]
    return f"https://t.me/{domain}/{post_id}"


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


divergence = Random()


def make_divergence(room_hash: int, event_id_hash: Optional[int] = None):
    seed = room_hash
    if event_id_hash:
        seed += event_id_hash
    divergence.seed(seed)
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
                raise NyxBotRuntimeError(
                    f"The day argument given ({args[0]}) is not vaild."
                )
            else:
                if (len(args) >= 2) and (args[1] == "all"):
                    sender = None

    return sender, days


RE_DATA = re.compile(
    r"""(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))"""
)


def strip_urls(input: str) -> str:
    return RE_DATA.sub("", input)


def should_record_message_content(room_features, room_id: str) -> bool:
    return room_features[room_id]["record_messages"]


def should_enable_jerryxiao(room_features, room_id: str) -> bool:
    return room_features[room_id]["jerryxiao"]


def should_enable_randomdraw(room_features, room_id: str) -> bool:
    return room_features[room_id]["randomdraw"]


def should_enable_join_confirm(room_features, room_id: str) -> bool:
    return room_features[room_id]["join_confirm"]


# A structure for a Matrix UID. It also supports legacy UID formats.
# First part: [\!-9\;-\~]+
# Matches legacy UIDs too.
# Second part:
# // IPv4 Address: [0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}
# // IPv6 Address: \[[0-9A-Fa-f:.]{2,45}\]
# // DNS name: [-.0-9A-Za-z]{1,255}
# // Port: [0-9]{1,5}
# // Hostname: [0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}|\[[0-9A-Fa-f:.]{2,45}\]|[-.0-9A-Za-z]{1,255}(?::[0-9]{1,5})?
MATRIX_UID_RE = r"@([\!-9\;-\~]+):([0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}|\[[0-9A-Fa-f:.]{2,45}\]|[-.0-9A-Za-z]{1,255}(?::[0-9]{1,5})?)"


def get_user_id_parts(user_id: str) -> Tuple[str, str]:
    uid, domain = re.match(MATRIX_UID_RE, user_id).groups()
    return (uid, domain)


REACTIONS = ["🎉", "🤣", "😃", "😋", "🥳", "🤔", "😅"]


def hash_user_id(user_id: str):
    hash = xxhash.xxh64_intdigest(user_id)
    return REACTIONS[hash % len(REACTIONS)]
