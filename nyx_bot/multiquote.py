from nio import AsyncClient, MatrixRoom, RoomMessageText
from wand.drawing import Drawing
from wand.image import Image

from nyx_bot.utils import make_single_quote_image, strip_beginning_quote


async def make_multiquote_image(
    client: AsyncClient,
    room: MatrixRoom,
    first_event: RoomMessageText,
    limit: int,
    replace_map: dict,
    self_event: RoomMessageText,
    command_prefix: str,
    forward: bool,
) -> Image:
    images = []
    show_user = True
    sender = None
    for next_event in await fetch_events(
        client, room, first_event, limit, self_event, command_prefix, forward
    ):
        show_user = sender != next_event.sender
        sender = next_event.sender
        if isinstance(next_event, RoomMessageText):
            next_quote_image = await make_single_quote_image(
                client, room, next_event, replace_map, show_user
            )
            images.append(next_quote_image)

    # Make the final quote image
    final_width = max(img.width for img in images)
    final_height = sum(img.height for img in images)

    ret = Image(width=int(final_width), height=int(final_height))
    render_y = 0
    with Drawing() as draw:
        for img in images:
            draw.composite("overlay", 0, render_y, img.width, img.height, img)
            render_y += img.height + 1
        draw(ret)
    return ret


async def fetch_events(
    client: AsyncClient,
    room: MatrixRoom,
    first_event: RoomMessageText,
    limit: int,
    self_event: RoomMessageText,
    command_prefix: str,
    forward: bool,
):
    events = []
    event_marker = first_event
    events.append(first_event)
    while len(events) < limit:
        context_resp = await client.room_context(room.room_id, event_marker.event_id)
        if forward:
            collected_events = context_resp.events_after
        else:
            collected_events = context_resp.events_before
        for event in collected_events:
            event_id = event.event_id
            # Ignore control message
            if event_id == self_event.event_id:
                continue
            # Only take actual text events
            if isinstance(event, RoomMessageText):
                event_body = strip_beginning_quote(event.body)
                has_command_prefix = event_body.startswith(command_prefix)
                if not has_command_prefix:
                    events.append(event)
            # Update event marker
            event_marker = event

    # Sort events
    events.sort(key=lambda ev: ev.server_timestamp)
    # Return them
    return events[:limit]
