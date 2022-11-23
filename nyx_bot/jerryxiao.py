import logging

from nio import AsyncClient, MatrixRoom, RoomGetEventError, RoomMessageText

from nyx_bot.chat_functions import make_pill, send_text_to_room

logger = logging.getLogger(__name__)


def make_jerryxiao_reply(from_sender: str, to_sender: str, ref: str, room: MatrixRoom):
    from_pill = make_pill(from_sender, room.user_name(from_sender))
    to_pill = make_pill(to_sender, room.user_name(to_sender))
    reply = ""
    reply_formatted = ""
    if len(ref) == 2 and ref[0] == ref[1]:
        reply = f"{room.user_name(from_sender)} {ref[0]}了{ref[1]} {room.user_name(to_sender)}"
        reply_formatted = f"{from_pill} {ref[0]}了{ref[1]} {to_pill}"
    elif ref.startswith("把") or ref.startswith("被"):
        action = ref[1:].lstrip()
        reply = f"{room.user_name(from_sender)} {ref[0]} {room.user_name(to_sender)} {action}"
        reply_formatted = f"{from_pill} {ref[0]} {to_pill} {action}"
    elif len(ref) == 3 and ref[1] == "一":
        reply = f"{room.user_name(from_sender)} {ref[0]}了{ref[1:]} {room.user_name(to_sender)}"
        reply_formatted = f"{from_pill} {ref[0]}了{ref[1:]} {to_pill}"
    elif ref.startswith("发动"):
        effect = ref[len("发动") :]
        reply = (
            f"{room.user_name(from_sender)} 向 {room.user_name(to_sender)} 发动了{effect}！"
        )
        reply_formatted = f"{from_pill} 向 {to_pill} 发动了{effect}！"
    else:
        reply = f"{room.user_name(from_sender)} {ref}了 {room.user_name(to_sender)}"
        reply_formatted = f"{from_pill} {ref}了 {to_pill}"
    return (reply, reply_formatted)


async def send_jerryxiao(
    client: AsyncClient,
    room: MatrixRoom,
    event: RoomMessageText,
    prefix: str,
    reply_to: str,
    reference_text: str,
    reversed_senders: bool = False,
):
    from_sender = event.sender
    target_event = await client.room_get_event(room.room_id, reply_to)
    if isinstance(target_event, RoomGetEventError):
        error = target_event.message
        logger.error(f"Failed to fetch event: {error}")
        return
    to_sender = target_event.event.sender
    action = reference_text[len(prefix) :]
    if action.isascii():
        return
    if action != "":
        if reversed_senders:
            # Swap from and to
            _tmp = from_sender
            from_sender = to_sender
            to_sender = _tmp
        send_text_tuple = make_jerryxiao_reply(from_sender, to_sender, action, room)
        send_text = send_text_tuple[0]
        send_text_formatted = send_text_tuple[1]
        await send_text_to_room(
            client,
            room.room_id,
            send_text_formatted,
            False,
            False,
            reply_to_event_id=event.event_id,
            literal_text_substitute=send_text,
        )
