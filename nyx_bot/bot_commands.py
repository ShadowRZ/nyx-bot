import logging
from calendar import THURSDAY
from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from nio import AsyncClient, MatrixRoom, RoomMessageImage, RoomMessageText, StickerEvent

from nyx_bot.chat_functions import (
    send_multiquote_image,
    send_quote_image,
    send_text_to_room,
    send_user_image,
)
from nyx_bot.config import Config
from nyx_bot.errors import NyxBotValueError
from nyx_bot.storage import MatrixMessage
from nyx_bot.utils import parse_matrixdotto_link

logger = logging.getLogger(__name__)


class Command:
    def __init__(
        self,
        client: AsyncClient,
        config: Config,
        command: str,
        room: MatrixRoom,
        event: RoomMessageText,
        reply_to: str,
        replace_map: dict,
    ):
        """A command made by a user.

        Args:
            client: The client to communicate to matrix with.

            config: Bot configuration parameters.

            command: The command and arguments.

            room: The room the command was sent in.

            event: The event describing the command.
        """
        self.client = client
        self.config = config
        self.command = command
        self.room = room
        self.event = event
        self.args = self.command.split()[1:]
        self.reply_to = reply_to
        self.replace_map = replace_map

    async def process(self):
        """Process the command"""
        if self.command.startswith("quote"):
            await self._quote()
        elif self.command.startswith("multiquote"):
            await self._multiquote()
        elif self.command.startswith("send_avatar"):
            await self._send_avatar()
        elif self.command.startswith("crazy_thursday"):
            await self._crazy_thursday()
        elif self.command.startswith("send_as_sticker"):
            await self._send_as_sticker()
        elif self.command.startswith("emit_statistics"):
            await self._stat()
        elif self.command.startswith("parse_matrixdotto"):
            await self._parse_matrixdotto()
        elif self.command.startswith("help"):
            await self._show_help()
        else:
            await self._unknown_command()

    async def _quote(self):
        """Make a new quote image. This command must be used on a reply."""
        await self.client.room_typing(self.room.room_id)
        await send_quote_image(
            self.client,
            self.room,
            self.event,
            self.reply_to,
            self.replace_map,
        )

    async def _multiquote(self):
        """Make a new multiquote image. This command must be used on a reply."""
        limit = 3
        if self.args:
            try:
                limit = int(self.args[0])
            except ValueError as e:
                raise NyxBotValueError("Please specify a integer.") from e
        if not (2 <= limit <= 6):
            raise NyxBotValueError("Please specify a integer in range [2, 6].")
        await self.client.room_typing(self.room.room_id)
        await send_multiquote_image(
            self.client,
            self.room,
            self.event,
            limit,
            self.reply_to,
            self.replace_map,
        )

    async def _stat(self):
        count = MatrixMessage.select().count()
        room_count = (
            MatrixMessage.select()
            .where(MatrixMessage.room_id == self.room.room_id)
            .count()
        )
        string = f"Total counted messages: {count}\nThis room: {room_count}"
        await send_text_to_room(
            self.client,
            self.room.room_id,
            string,
            markdown_convert=False,
            reply_to_event_id=self.event.event_id,
            literal_text=True,
        )

    async def _crazy_thursday(self):
        today = date.today()
        now = datetime.now()
        next_thursday = today + relativedelta(
            weekday=THURSDAY, hour=0, minute=0, second=0
        )
        next_thur_date = next_thursday.date()
        if today == next_thur_date:
            string = "Crazy Thursday !!"
        else:
            dt = next_thursday - now
            string = (
                f"Time until next thursday ({next_thur_date.isoformat()}): {str(dt)}"
            )
        await send_text_to_room(
            self.client,
            self.room.room_id,
            string,
            notice=False,
            markdown_convert=False,
            reply_to_event_id=self.event.event_id,
            literal_text=True,
        )

    async def _parse_matrixdotto(self):
        if not self.args:
            raise NyxBotValueError("No matrix.to links given.")
        string = "Parse results:\n"
        for i in self.args:
            result = parse_matrixdotto_link(i)
            if not result:
                string += f"{i}: Invaild\n"
            else:
                type_ = result[0]
                if type_ == "user":
                    string += f"{i}: User, ID: {result[1]}\n"
                elif type_ == "room":
                    string += f"{i}: Room, ID: {result[1]}\n"
                elif type_ == "room_named":
                    string += f"{i}: Named Room, ID: {result[1]}\n"
                elif type_ == "event":
                    string += (
                        f"{i}: Room Event, Room: {result[1]} Event ID: {result[2]}\n"
                    )
        await send_text_to_room(
            self.client,
            self.room.room_id,
            string,
            markdown_convert=False,
            reply_to_event_id=self.event.event_id,
            literal_text=True,
        )

    async def _send_avatar(self):
        """\
Send an avatar.

When used in a reply, send the avatar of the person being replied to.
Outside of a reply, send the avatar of the command sender.\
"""
        await send_user_image(self.client, self.room, self.event, self.reply_to)

    async def _send_as_sticker(self):
        """Turn an image into a sticker. This command must be used on a reply."""
        if not self.reply_to:
            raise NyxBotValueError("Please reply to a image message.")
        target_response = await self.client.room_get_event(
            self.room.room_id, self.reply_to
        )
        target_event = target_response.event
        if isinstance(target_event, RoomMessageImage):
            content = target_event.source.get("content")
            info = content["info"]
            if "thumbnail_info" not in content:
                # Populate Thumbnail info
                info["thumbnail_info"] = {
                    "w": info["w"],
                    "h": info["h"],
                    "size": info["size"],
                    "mimetype": info["mimetype"],
                }
            if "thumbnail_url" not in content:
                # Populate Thumbnail URL
                info["thumbnail_url"] = content["url"]
            content["info"] = info
            del content["msgtype"]
            matrixdotto_url = (
                f"https://matrix.to/#/{self.room.room_id}/{target_event.event_id}"
            )
            content["body"] = f"Sticker of {matrixdotto_url}"
            content["m.relates_to"] = {
                "m.in_reply_to": {"event_id": self.event.event_id}
            }
            await self.client.room_send(
                self.room.room_id, message_type="m.sticker", content=content
            )
        elif isinstance(target_event, StickerEvent):
            raise NyxBotValueError("This message is already a sticker.")
        else:
            raise NyxBotValueError("Please reply to a image message.")

    async def _show_help(self):
        """Show the help text"""
        if not self.args:
            text = (
                "Nyx Bot via matrix-nio\n\nUse `help commands` to view "
                "available commands."
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        topic = self.args[0]
        if topic == "commands":
            text = """\
Available commands:

* `quote`: Make a new quote image. This command must be used on a reply.
* `send_avatar`: Send an avatar. When used in a reply, send the avatar of the person being replied to. Outside of a reply, send the avatar of the command sender.
* `send_as_sticker`: Turn an image into a sticker. This command must be used on a reply.
* `multiquote [count]`: (count is in [2, 6]) Make a new multiquote image. This command must be used on a reply.
"""
        else:
            text = "Unknown help topic!"
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )
