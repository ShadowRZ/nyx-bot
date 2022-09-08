import logging
from io import BytesIO
from typing import Optional, Union
from urllib.parse import urlparse

from markdown import markdown
from nio import (
    AsyncClient,
    ErrorResponse,
    MatrixRoom,
    RoomMessageText,
    RoomSendResponse,
    SendRetryError,
    UploadResponse,
)
from wand.image import Image

from nyx_bot.quote_image import make_quote_image

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

    content = {
        "msgtype": msgtype,
        "body": message,
    }

    if not literal_text:
        content["format"] = "org.matrix.custom.html"

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


async def send_quote_image(
    client: AsyncClient,
    room: MatrixRoom,
    event: RoomMessageText,
    reply_to: str,
):
    if not reply_to:
        await send_text_to_room(
            client,
            room.room_id,
            "Please reply to a text message.",
            True,
            False,
            event.event_id,
            True,
        )
        return
    target_response = await client.room_get_event(room.room_id, reply_to)
    target_event = target_response.event
    if isinstance(target_event, RoomMessageText):
        sender = target_event.sender
        body = target_event.body
        sender_name = room.user_name(sender)
        sender_avatar = room.avatar_url(sender)
        image = None
        if sender_avatar:
            url = urlparse(sender_avatar)
            server_name = url.netloc
            media_id = url.path.replace("/", "")
            avatar_resp = await client.download(server_name, media_id)
            data = avatar_resp.body
            bytesio = BytesIO(data)
            image = Image(file=bytesio)
        else:
            image = Image(width=64, height=64, background="#FFFF00")
        quote_image = await make_quote_image(sender_name, body, image)
        await send_sticker_image(client, room.room_id, quote_image, reply_to)

    else:
        await send_text_to_room(
            client,
            room.room_id,
            "Please reply to a normal text message.",
            True,
            False,
            event.event_id,
            True,
        )


async def send_sticker_image(
    client: AsyncClient,
    room_id: str,
    image: Image,
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
        "body": "[Image]",
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
        "msgtype": "m.image",
        "url": resp.content_uri,
    }

    if reply_to:
        content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}

    try:
        await client.room_send(room_id, message_type="m.sticker", content=content)
        print("Image was sent successfully")
    except Exception:
        print(f"Image send of file {image} failed.")
