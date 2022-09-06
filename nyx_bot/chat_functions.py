import logging
from typing import Optional, Union

from markdown import markdown
from nio import (
    AsyncClient,
    ErrorResponse,
    MatrixRoom,
    MegolmEvent,
    Response,
    RoomMessageText,
    RoomSendResponse,
    SendRetryError,
)

logger = logging.getLogger(__name__)


async def send_text_to_room(
    client: AsyncClient,
    room_id: str,
    message: str,
    notice: bool = True,
    markdown_convert: bool = True,
    reply_to_event_id: Optional[str] = None,
) -> Union[RoomSendResponse, ErrorResponse]:
    """Send text to a matrix room.

    Args:
        client: The client to communicate to matrix with.

        room_id: The ID of the room to send the message to.

        message: The message content.

        notice: Whether the message should be sent with an "m.notice" message type
            (will not ping users).

        markdown_convert: Whether to convert the message content to markdown.
            Defaults to true.

        reply_to_event_id: Whether this message is a reply to another event. The event
            ID this is message is a reply to.

    Returns:
        A RoomSendResponse if the request was successful, else an ErrorResponse.
    """
    # Determine whether to ping room members or not
    msgtype = "m.notice" if notice else "m.text"

    content = {
        "msgtype": msgtype,
        "format": "org.matrix.custom.html",
        "body": message,
    }

    if markdown_convert:
        content["formatted_body"] = markdown(message)

    if reply_to_event_id:
        content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to_event_id}}

    try:
        return await client.room_send(
            room_id,
            "m.room.message",
            content,
            ignore_unverified_devices=True,
        )
    except SendRetryError:
        logger.exception(f"Unable to send message response to {room_id}")


def make_pill(user_id: str, displayname: str = None) -> str:
    """Convert a user ID (and optionally a display name) to a formatted user 'pill'

    Args:
        user_id: The MXID of the user.

        displayname: An optional displayname. Clients like Element will figure out the
            correct display name no matter what, but other clients may not. If not
            provided, the MXID will be used instead.

    Returns:
        The formatted user pill.
    """
    if not displayname:
        # Use the user ID as the displayname if not provided
        displayname = user_id

    return f'<a href="https://matrix.to/#/{user_id}">{displayname}</a>'


def make_jerryxiao_reply(
    from_sender: str, to_sender: str, ref: str, room: MatrixRoom
):
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
    else:
        reply = f"{room.user_name(from_sender)} {ref}了 {room.user_name(to_sender)}"
        reply_formatted = f"{from_pill} {ref}了 {to_pill}"
    return (reply, reply_formatted)


async def send_in_reply_to(
    client: AsyncClient,
    room_id: str,
    event: RoomMessageText,
    body: str,
    formatted_body: str,
) -> Union[RoomSendResponse, ErrorResponse]:
    content = {
        "msgtype": "m.text",
        "format": "org.matrix.custom.html",
        "body": body,
        "formatted_body": formatted_body,
    }
    content["m.relates_to"] = {"m.in_reply_to": {"event_id": event.event_id}}
    try:
        return await client.room_send(
            room_id,
            "m.room.message",
            content,
            ignore_unverified_devices=True,
        )
    except SendRetryError:
        logger.exception(f"Unable to send message response to {room_id}")


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
    to_sender = target_event.event.sender
    action = reference_text[len(prefix) :]
    if action != "":
        if reversed_senders:
            # Swap from and to
            _tmp = from_sender
            from_sender = to_sender
            to_sender = _tmp
        send_text_tuple = make_jerryxiao_reply(from_sender, to_sender, action, room)
        send_text = send_text_tuple[0]
        send_text_formatted = send_text_tuple[1]
        await send_in_reply_to(
            client, room.room_id, event, send_text, send_text_formatted
        )


async def react_to_event(
    client: AsyncClient,
    room_id: str,
    event_id: str,
    reaction_text: str,
) -> Union[Response, ErrorResponse]:
    """Reacts to a given event in a room with the given reaction text

    Args:
        client: The client to communicate to matrix with.

        room_id: The ID of the room to send the message to.

        event_id: The ID of the event to react to.

        reaction_text: The string to react with. Can also be (one or more) emoji characters.

    Returns:
        A nio.Response or nio.ErrorResponse if an error occurred.

    Raises:
        SendRetryError: If the reaction was unable to be sent.
    """
    content = {
        "m.relates_to": {
            "rel_type": "m.annotation",
            "event_id": event_id,
            "key": reaction_text,
        }
    }

    return await client.room_send(
        room_id,
        "m.reaction",
        content,
        ignore_unverified_devices=True,
    )


async def decryption_failure(self, room: MatrixRoom, event: MegolmEvent) -> None:
    """Callback for when an event fails to decrypt. Inform the user"""
    logger.error(
        f"Failed to decrypt event '{event.event_id}' in room '{room.room_id}'!"
        f"\n\n"
        f"Tip: try using a different device ID in your config file and restart."
        f"\n\n"
        f"If all else fails, delete your store directory and let the bot recreate "
        f"it (your reminders will NOT be deleted, but the bot may respond to existing "
        f"commands a second time)."
    )

    user_msg = (
        "Unable to decrypt this message. "
        "Check whether you've chosen to only encrypt to trusted devices."
    )

    await send_text_to_room(
        self.client,
        room.room_id,
        user_msg,
        reply_to_event_id=event.event_id,
    )
