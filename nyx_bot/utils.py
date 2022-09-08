from typing import Optional

from nio import AsyncClient, MatrixRoom


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
