import logging
from calendar import THURSDAY
from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from nio import (
    AsyncClient,
    MatrixRoom,
    RoomGetEventError,
    RoomMessageImage,
    RoomMessageText,
    StickerEvent,
)

from nyx_bot.archcn_utils import send_archlinuxcn_pkg, update_archlinuxcn_pkg
from nyx_bot.chat_functions import (
    bulk_update_messages,
    send_multiquote_image,
    send_quote_image,
    send_text_to_room,
    send_user_image,
)
from nyx_bot.config import Config
from nyx_bot.errors import NyxBotRuntimeError, NyxBotValueError
from nyx_bot.storage import MatrixMessage, MembershipUpdates, UserTag
from nyx_bot.utils import make_divergence, parse_matrixdotto_link

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
        command_prefix: str,
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
        self.command_prefix = command_prefix

    async def process(self):
        """Process the command"""
        if self.command.startswith("quote"):
            await self._quote()
        elif self.command.startswith("archlinuxcn"):
            await self._archlinuxcn()
        elif self.command.startswith("update_archlinuxcn"):
            await self._update_archlinuxcn()
        elif self.command.startswith("multiquote"):
            await self._multiquote(False)
        elif self.command.startswith("forward_multiquote"):
            await self._multiquote(True)
        elif self.command.startswith("send_avatar"):
            await self._send_avatar()
        elif self.command.startswith("avatar_changes"):
            await self._avatar_changes()
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
        elif self.command.startswith("tag"):
            await self._tag()
        elif self.command.startswith("remove_tag"):
            await self._remove_tag()
        elif self.command.startswith("update"):
            await self._update()
        elif self.command.startswith("room_id"):
            await self._room_id()
        elif self.command.startswith("divergence"):
            await self._divergence()
        else:
            await self._unknown_command()

    async def _quote(self):
        """Make a new quote image. This command must be used on a reply."""
        if not self.reply_to:
            raise NyxBotValueError("Please reply to a text message.")
        await self.client.room_typing(self.room.room_id)
        await send_quote_image(
            self.client,
            self.room,
            self.event,
            self.reply_to,
            self.replace_map,
        )

    async def _archlinuxcn(self):
        if not self.args:
            raise NyxBotValueError("No package given.")
        await send_archlinuxcn_pkg(self.client, self.room, self.event, self.args[0])

    async def _avatar_changes(self):
        if not self.reply_to:
            raise NyxBotValueError(
                "Please reply to a message for sending avatar changes."
            )
        await self.client.room_typing(self.room.room_id)
        target_response = await self.client.room_get_event(
            self.room.room_id, self.reply_to
        )
        if isinstance(target_response, RoomGetEventError):
            error = target_response.message
            raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
        target_sender = target_response.event.sender
        changes = (
            MembershipUpdates.select()
            .where(
                (MembershipUpdates.room_id == self.room.room_id)
                & (MembershipUpdates.state_key == target_sender)
            )
            .order_by(MembershipUpdates.origin_server_ts.desc())
        )
        send_text = ""
        i = 0
        sender_avatar = self.room.avatar_url(target_sender)
        avatar_http = await self.client.mxc_to_http(sender_avatar)
        send_text += f"Current Avatar: {avatar_http}\n"
        for change in changes:
            avatar_url = change.avatar_url
            prev_avatar_url = change.prev_avatar_url
            if avatar_url != prev_avatar_url:
                i -= 1
                avatar_http = await self.client.mxc_to_http(avatar_url)
                send_text += (
                    f"{i}: Changed to {avatar_http} ({change.datetime.isoformat()})\n"
                )
            if i < -3:
                break
        await self.client.room_typing(self.room.room_id, False)
        await send_text_to_room(
            self.client,
            self.room.room_id,
            send_text.rstrip(),
            notice=False,
            markdown_convert=False,
            reply_to_event_id=self.event.event_id,
            literal_text=True,
        )

    async def _update_archlinuxcn(self):
        await self.client.room_typing(self.room.room_id)
        await update_archlinuxcn_pkg(self.client, self.room, self.event)

    async def _update(self):
        await self.client.room_typing(self.room.room_id)
        context_resp = await self.client.room_context(
            self.room.room_id, self.event.event_id
        )
        start_token = context_resp.start
        await bulk_update_messages(self.client, self.room, start_token)
        await self.client.room_typing(self.room.room_id, False)
        await send_text_to_room(
            self.client,
            self.room.room_id,
            "Done.",
            notice=False,
            markdown_convert=False,
            reply_to_event_id=self.event.event_id,
            literal_text=True,
        )

    async def _room_id(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            self.room.room_id,
            notice=False,
            markdown_convert=False,
            reply_to_event_id=self.event.event_id,
            literal_text=True,
        )

    async def _divergence(self):
        text = "%f%%" % make_divergence(self.room)
        await send_text_to_room(
            self.client,
            self.room.room_id,
            text,
            notice=False,
            markdown_convert=False,
            reply_to_event_id=self.event.event_id,
            literal_text=True,
        )

    async def _multiquote(self, forward: bool):
        """Make a new multiquote image. This command must be used on a reply."""
        if not self.reply_to:
            raise NyxBotValueError("Please reply to a text message.")
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
            self.command_prefix,
            forward,
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
            notice=False,
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
        if isinstance(target_response, RoomGetEventError):
            error = target_response.message
            raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
        target_event = target_response.nse.event
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
        text = (
            "Nyx Bot via matrix-nio\n\nCommands reference is avaliable at "
            "https://github.com/ShadowRZ/nyx-bot/blob/master/COMMANDS.md"
        )
        await send_text_to_room(self.client, self.room.room_id, text, notice=False)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
            notice=False,
            markdown_convert=False,
            reply_to_event_id=self.event.event_id,
            literal_text=True,
        )

    async def _tag(self):
        if not self.reply_to:
            raise NyxBotValueError("Please reply to a message.")
        target_event = await self.client.room_get_event(
            self.room.room_id, self.reply_to
        )
        if isinstance(target_event, RoomGetEventError):
            error = target_event.message
            raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
        sender = target_event.event.sender
        if not self.args:
            user_tag = UserTag.get_or_none(
                (UserTag.room_id == self.room.room_id) & (UserTag.sender == sender)
            )
            if user_tag:
                tag_name = f"#{user_tag.tag}"
            else:
                tag_name = "(None)"
            await send_text_to_room(
                self.client,
                self.room.room_id,
                f"Tag for {sender}: {tag_name}",
                notice=False,
                markdown_convert=False,
                reply_to_event_id=self.event.event_id,
                literal_text=True,
            )
        else:
            new_tag = self.args[0]
            if new_tag.startswith("#"):
                tag_name = new_tag[1:]
                if tag_name == "":
                    raise NyxBotValueError("Tag is empty.")
                else:
                    UserTag.update_user_tag(self.room.room_id, sender, tag_name)
                    await send_text_to_room(
                        self.client,
                        self.room.room_id,
                        "Done.",
                        notice=False,
                        markdown_convert=False,
                        reply_to_event_id=self.event.event_id,
                        literal_text=True,
                    )
            else:
                raise NyxBotValueError("Tag is invaild: Tag should start with #.")

    async def _remove_tag(self):
        if not self.reply_to:
            raise NyxBotValueError("Please reply to a message.")
        target_event = await self.client.room_get_event(
            self.room.room_id, self.reply_to
        )
        if isinstance(target_event, RoomGetEventError):
            error = target_event.message
            raise NyxBotRuntimeError(f"Failed to fetch event: {error}")
        sender = target_event.event.sender
        UserTag.delete_user_tag(self.room.room_id, sender)
