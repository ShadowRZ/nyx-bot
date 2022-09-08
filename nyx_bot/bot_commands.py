import logging

from nio import AsyncClient, MatrixRoom, RoomMessageText

from nyx_bot.chat_functions import send_quote_image, send_text_to_room, send_user_image
from nyx_bot.config import Config
from nyx_bot.storage import Storage

logger = logging.getLogger(__name__)


class Command:
    def __init__(
        self,
        client: AsyncClient,
        store: Storage,
        config: Config,
        command: str,
        room: MatrixRoom,
        event: RoomMessageText,
        reply_to: str,
    ):
        """A command made by a user.

        Args:
            client: The client to communicate to matrix with.

            store: Bot storage.

            config: Bot configuration parameters.

            command: The command and arguments.

            room: The room the command was sent in.

            event: The event describing the command.
        """
        self.client = client
        self.store = store
        self.config = config
        self.command = command
        self.room = room
        self.event = event
        self.args = self.command.split()[1:]
        self.reply_to = reply_to

    async def process(self):
        """Process the command"""
        if self.command.startswith("quote"):
            await self._quote()
        elif self.command.startswith("send_avatar"):
            await self._send_avatar()
        elif self.command.startswith("help"):
            await self._show_help()
        else:
            await self._unknown_command()

    async def _quote(self):
        await send_quote_image(self.client, self.room, self.event, self.reply_to)

    async def _send_avatar(self):
        await send_user_image(self.client, self.room, self.event, self.reply_to)

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
            text = "Available commands:\n\n* `quote`: Make a new quote image. This command must be used on a reply.\n* `send_avatar`: Send the avatar of the person being replied to. This command must be used on a reply."
        else:
            text = "Unknown help topic!"
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )
