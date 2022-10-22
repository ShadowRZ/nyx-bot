import logging
import re
from html import escape
from io import BytesIO
from typing import Optional, Union

import magic
from markdown import markdown
from nio import (
    AsyncClient,
    DownloadError,
    ErrorResponse,
    MatrixRoom,
    RedactedEvent,
    RoomGetEventError,
    RoomMessageFormatted,
    RoomMessageMedia,
    RoomMessageText,
    RoomSendResponse,
    SendRetryError,
    StickerEvent,
    UploadResponse,
)
from wand.image import Image

from nyx_bot.errors import NyxBotRuntimeError, NyxBotValueError
from nyx_bot.multiquote import make_multiquote_image
from nyx_bot.storage import MatrixMessage
from nyx_bot.utils import (
    get_body,
    get_external_url,
    get_replaces,
    make_datetime,
    make_single_quote_image,
    strip_beginning_quote,
)

logger = logging.getLogger(__name__)


async def send_text_to_room(
    client: AsyncClient,
    room_id: str,
    message: str,
    notice: bool = True,
    markdown_convert: bool = True,
    reply_to_event_id: Optional[str] = None,
    literal_text: Optional[bool] = False,
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

    body = ""
    formatted_body = ""

    # Don't even try to make <mx-reply> if we're sending a notice
    target_event = None
    if (not notice) and reply_to_event_id:
        target_resp = await client.room_get_event(room_id, reply_to_event_id)
        if isinstance(target_resp, RoomGetEventError):
            error = target_resp.message
            logger.error(f"Failed to fetch event: {error}")
        else:
            target_event = target_resp.event
            matrixdotto_url = f"https://matrix.to/#/{room_id}/{target_event.event_id}"
            pill = make_pill(target_event.sender)
            formatted_body += f'<mx-reply><blockquote><a href="{matrixdotto_url}">In reply to</a> {pill}<br/>'
    # A text message
    if isinstance(target_event, RoomMessageFormatted):
        if target_event.formatted_body:
            # Strip <mx-reply>
            string = re.sub(r"<mx-reply>.*</mx-reply>", "", target_event.formatted_body)
            formatted_body += string
        else:
            # Unlike Element, escape text body
            formatted_body += escape(target_event.body).replace("\n", "</br>")
        formatted_body += "</blockquote></mx-reply>"
        ref_body = strip_beginning_quote(
            await get_body(client, room_id, target_event.event_id)
        )
        body += f"> <{target_event.sender}> "
        body += ref_body.rstrip().replace("\n", "\n> ")
        body += "\n\n"
    # Sticker or media
    elif isinstance(target_event, RoomMessageMedia):
        # Event body should just be intepreted as text, escape it
        formatted_body += escape(target_event.body or "[Media]").replace("\n", "</br>")
        formatted_body += "</blockquote></mx-reply>"
        ref_body = strip_beginning_quote(
            await get_body(client, room_id, target_event.event_id)
        )
        body += f"> <{target_event.sender}> "
        body += ref_body.rstrip().replace("\n", "\n> ")
        body += "\n\n"
    elif isinstance(target_event, StickerEvent):
        # Event body should just be intepreted as text, escape it
        formatted_body += escape(target_event.body or "[Sticker]").replace(
            "\n", "</br>"
        )
        formatted_body += "</blockquote></mx-reply>"
        ref_body = strip_beginning_quote(
            await get_body(client, room_id, target_event.event_id)
        )
        body += f"> <{target_event.sender}> "
        body += ref_body.rstrip().replace("\n", "\n> ")
        body += "\n\n"

    body += message

    content = {
        "msgtype": msgtype,
        "body": body,
    }

    if markdown_convert:
        formatted_body += markdown(message)
    else:
        # So HTML can be directly written
        if literal_text:
            message = message.replace("\n", "<br/>")
        formatted_body += message

    # Two cases for forcing HTML:
    # 1. we're not sending literal text
    # 2. it has a reply target
    if (not literal_text) or reply_to_event_id:
        content["format"] = "org.matrix.custom.html"
        content["formatted_body"] = formatted_body

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


async def send_multiquote_image(
    client: AsyncClient,
    room: MatrixRoom,
    event: RoomMessageText,
    limit: int,
    reply_to: str,
    replace_map: dict,
    command_prefix: str,
    forward: bool,
):
    target_response = await client.room_get_event(room.room_id, reply_to)
    if isinstance(target_response, RoomGetEventError):
        error = target_response.message
        raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
    target_event = target_response.event
    if isinstance(target_event, RedactedEvent):
        raise NyxBotRuntimeError("You can't start a multiquote on a redacted event.")
    elif isinstance(target_event, RoomMessageText):
        quote_image = await make_multiquote_image(
            client,
            room,
            target_event,
            limit,
            replace_map,
            event,
            command_prefix,
            forward,
        )
        await send_sticker_image(
            client, room.room_id, quote_image, "[Multiquote]", event.event_id
        )
        await client.room_typing(room.room_id, False)
    else:
        raise NyxBotValueError(
            "You can't start a multiquote on an event that is not a normal text message."
        )


async def send_quote_image(
    client: AsyncClient,
    room: MatrixRoom,
    event: RoomMessageText,
    reply_to: str,
    replace_map: dict,
):
    target_response = await client.room_get_event(room.room_id, reply_to)
    if isinstance(target_response, RoomGetEventError):
        error = target_response.message
        raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
    target_event = target_response.event
    if isinstance(target_event, RedactedEvent):
        raise NyxBotRuntimeError("Event has been redacted.")
    elif isinstance(target_event, RoomMessageText):
        quote_image = await make_single_quote_image(
            client, room, target_event, replace_map, True
        )
        matrixdotto_url = f"https://matrix.to/#/{room.room_id}/{target_event.event_id}"
        await send_sticker_image(
            client, room.room_id, quote_image, matrixdotto_url, event.event_id
        )
        await client.room_typing(room.room_id, False)
    else:
        raise NyxBotValueError("Please reply to a normal text message.")


async def send_sticker_image(
    client: AsyncClient,
    room_id: str,
    image: Image,
    body: str,
    reply_to: Optional[str] = None,
):
    """Send sticker to toom. Hardcodes to WebP.

    Arguments:
    ---------
    client : Client
    room_id : str
    image : Image

    This is a working example for a JPG image.
        "content": {
            "body": "someimage.jpg",
            "info": {
                "size": 5420,
                "mimetype": "image/jpeg",
                "thumbnail_info": {
                    "w": 100,
                    "h": 100,
                    "mimetype": "image/jpeg",
                    "size": 2106
                },
                "w": 100,
                "h": 100,
                "thumbnail_url": "mxc://example.com/SomeStrangeThumbnailUriKey"
            },
            "msgtype": "m.image",
            "url": "mxc://example.com/SomeStrangeUriKey"
        }

    """
    (width, height) = (image.width, image.height)

    bytesio = BytesIO()
    with image:
        image.format = "webp"
        image.save(file=bytesio)
    length = bytesio.getbuffer().nbytes
    bytesio.seek(0)
    logger.debug(f"Sending Image with length {length}, width={width}, height={height}")

    resp, maybe_keys = await client.upload(
        bytesio,
        content_type="image/webp",  # image/jpeg
        filename="image.webp",
        filesize=length,
    )
    if isinstance(resp, UploadResponse):
        print("Image was uploaded successfully to server. ")
    else:
        print(f"Failed to upload image. Failure response: {resp}")

    content = {
        "body": body,
        "info": {
            "size": length,
            "mimetype": "image/webp",
            "thumbnail_info": {
                "mimetype": "image/webp",
                "size": length,
                "w": width,  # width in pixel
                "h": height,  # height in pixel
            },
            "w": width,  # width in pixel
            "h": height,  # height in pixel
            "thumbnail_url": resp.content_uri,
        },
        "url": resp.content_uri,
    }

    if reply_to:
        content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}

    try:
        await client.room_send(room_id, message_type="m.sticker", content=content)
        print("Image was sent successfully")
    except Exception:
        print(f"Image send of file {image} failed.")


async def send_user_image(
    client: AsyncClient,
    room: MatrixRoom,
    event: RoomMessageText,
    reply_to: str,
):
    """Send a user's avatar to a room."""
    if not reply_to:
        target_event = event
    else:
        target_response = await client.room_get_event(room.room_id, reply_to)
        if isinstance(target_response, RoomGetEventError):
            error = target_response.message
            raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
        target_event = target_response.event
    sender = target_event.sender
    sender_name = room.user_name(sender)
    sender_avatar = room.avatar_url(sender)
    image = None
    length = 0
    mimetype = None
    if sender_avatar:
        avatar_resp = await client.download(mxc=sender_avatar)
        if isinstance(avatar_resp, DownloadError):
            error = avatar_resp.message
            raise NyxBotRuntimeError(f"Failed to download {sender_avatar}: {error}")
        data = avatar_resp.body
        mimetype = magic.from_buffer(data, mime=True)
        bytesio = BytesIO(data)
        length = bytesio.getbuffer().nbytes
        image = Image(file=bytesio)
    else:
        await send_text_to_room(
            client,
            room.room_id,
            "This user has no avatar.",
            False,
            False,
            event.event_id,
            True,
        )
        return

    with image:
        (width, height) = (image.width, image.height)

    content = {
        "body": f"[Avatar of {sender_name}]",
        "info": {
            "size": length,
            "mimetype": mimetype,
            "thumbnail_info": {
                "mimetype": mimetype,
                "size": length,
                "w": width,  # width in pixel
                "h": height,  # height in pixel
            },
            "w": width,  # width in pixel
            "h": height,  # height in pixel
            "thumbnail_url": sender_avatar,
        },
        "msgtype": "m.image",
        "url": sender_avatar,
    }

    content["m.relates_to"] = {"m.in_reply_to": {"event_id": event.event_id}}

    await client.room_send(room.room_id, message_type="m.room.message", content=content)


async def send_exception(
    client: AsyncClient,
    inst: Exception,
    room_id: str,
    event_id: Optional[str] = None,
):
    if isinstance(inst, NyxBotValueError):
        string = f"Your input is invalid: {str(inst)}"
    elif isinstance(inst, NyxBotRuntimeError):
        string = f"Your request couldn't be sastified: {str(inst)}"
    else:
        string = f"An Exception occured:\n{type(inst).__name__}"
        exception_str = str(inst)
        if str != "":
            string += f": {exception_str}"
        logger.exception(string)
    await send_text_to_room(
        client,
        room_id,
        string,
        notice=False,
        markdown_convert=False,
        reply_to_event_id=event_id,
        literal_text=True,
    )


async def bulk_update_messages(
    client: AsyncClient,
    room: MatrixRoom,
    start: str,
    limit: int = 500,
):
    count = 0
    sync_token = start
    while count <= limit:
        messages_resp = await client.room_messages(room.room_id, sync_token, limit=50)
        messages = messages_resp.chunk
        sorted_messages = sorted(messages, key=lambda ev: ev.server_timestamp)
        for event in sorted_messages:
            if isinstance(event, RoomMessageText):
                event_replace = get_replaces(event)
                timestamp = make_datetime(event.server_timestamp)
                external_url = get_external_url(event)
                MatrixMessage.update_message(
                    room, event, external_url, timestamp, event_replace
                )
                count += 1
        sync_token = messages_resp.end
