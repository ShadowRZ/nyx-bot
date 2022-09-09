from datetime import datetime
from typing import Optional
from urllib.parse import unquote, urlparse

from nio import AsyncClient, Event, MatrixRoom


def user_name(room: MatrixRoom, user_id: str) -> Optional[str]:
    """Get display name for a user."""
    if user_id not in room.users:
        return None
    user = room.users[user_id]
    return user.name


async def get_body(
    client: AsyncClient, room: MatrixRoom, event_id: str, replace_map: str
) -> str:
    if event_id not in replace_map:
        target_response = await client.room_get_event(room.room_id, event_id)
        target_event = target_response.event
        return target_event.body
    else:
        new_evid = replace_map.get(event_id)
        target_response = await client.room_get_event(room.room_id, new_evid)
        target_event = target_response.event
        content = target_event.source.get("content")
        new_content = content.get("m.new_content")
        return new_content.get("body")


async def get_formatted_body(
    client: AsyncClient, room: MatrixRoom, event_id: str, replace_map: str
) -> Optional[str]:
    if event_id not in replace_map:
        target_response = await client.room_get_event(room.room_id, event_id)
        target_event = target_response.event
        return target_event.formatted_body
    else:
        new_evid = replace_map.get(event_id)
        target_response = await client.room_get_event(room.room_id, new_evid)
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
        return (type_, identifier, None)
    elif len(paths) == 3:
        # Must be an event ID
        room = unquote(paths[1])
        event_id = unquote(paths[2])
        return ("event", room, event_id)
