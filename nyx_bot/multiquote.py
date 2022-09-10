from nio import AsyncClient, MatrixRoom, RoomMessageText
from wand.drawing import Drawing
from wand.image import Image

from nyx_bot.storage import MatrixMessage
from nyx_bot.utils import make_single_quote_image


async def make_multiquote_image(
    client: AsyncClient,
    room: MatrixRoom,
    first_event: RoomMessageText,
    limit: int,
    replace_map: dict,
    self_event: RoomMessageText,
) -> Image:
    # First find all events
    event_ts = first_event.server_timestamp
    images = []
    i = 1
    sender = first_event.sender
    first_quote_image = await make_single_quote_image(
        client, room, first_event, replace_map, True
    )
    images.append(first_quote_image)
    for event_db_item in MatrixMessage.select().where(
        (MatrixMessage.origin_server_ts > event_ts)
        & (MatrixMessage.room_id == room.room_id)
    ):
        event_id = event_db_item.event_id
        if event_id == self_event.event_id:
            continue
        if event_db_item.is_replacement:
            continue
        next_response = await client.room_get_event(room.room_id, event_id)
        next_event = next_response.event
        if isinstance(next_event, RoomMessageText):
            show_user = sender != next_event.sender
            next_quote_image = await make_single_quote_image(
                client, room, next_event, replace_map, show_user
            )
            images.append(next_quote_image)
            sender = next_event.sender
            i += 1
        if i >= limit:
            break

    # Next make the final quote image
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
