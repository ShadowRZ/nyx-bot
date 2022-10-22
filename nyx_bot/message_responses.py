import logging
import re
from zlib import crc32

from nio import AsyncClient, MatrixRoom, RoomMessageText

from nyx_bot.chat_functions import gen_result_randomdraw, send_text_to_room
from nyx_bot.config import Config
from nyx_bot.jerryxiao import send_jerryxiao

logger = logging.getLogger(__name__)


class Message:
    def __init__(
        self,
        client: AsyncClient,
        config: Config,
        message_content: str,
        room: MatrixRoom,
        event: RoomMessageText,
        reply_to: str,
        disable_jerryxiao_for,
    ):
        """Initialize a new Message

        Args:
            client: nio client used to interact with matrix.

            config: Bot configuration parameters.

            message_content: The body of the message.

            room: The room the event came from.

            event: The event defining the message.
        """
        self.client = client
        self.config = config
        self.message_content = message_content
        self.room = room
        self.event = event
        self.reply_to = reply_to
        self.disable_jerryxiao_for = disable_jerryxiao_for

    async def process(self) -> None:
        """Process and possibly respond to the message"""
        if re.match("^(!!|\\\\|/|¡¡)", self.message_content):
            await self._jerryxiao()
        elif self.message_content.startswith("@@"):
            query = self.message_content[2:]
            await self._randomdraw(query, False)
        elif self.message_content.startswith("@%"):
            query = self.message_content[2:]
            await self._randomdraw(query, True)

    async def _randomdraw(self, query: str, prob: bool) -> None:
        sender = self.event.sender
        msg = gen_result_randomdraw(
            self.room,
            query.strip(),
            sender,
            crc32(sender.encode()),
            prob,
        )
        await send_text_to_room(
            self.client,
            self.room.room_id,
            msg,
            notice=False,
            markdown_convert=False,
            reply_to_event_id=self.event.event_id,
            literal_text=True,
        )

    async def _jerryxiao(self) -> None:
        """Performs features similar to the bot created by Jerry Xiao"""
        if self.room.room_id in self.disable_jerryxiao_for:
            return
        msg = self.message_content
        if msg.startswith("/"):
            await send_jerryxiao(
                self.client, self.room, self.event, "/", self.reply_to, msg
            )
        elif msg.startswith("!!"):
            await send_jerryxiao(
                self.client, self.room, self.event, "!!", self.reply_to, msg
            )
        elif msg.startswith("\\"):
            await send_jerryxiao(
                self.client, self.room, self.event, "\\", self.reply_to, msg, True
            )
        elif msg.startswith("¡¡"):
            await send_jerryxiao(
                self.client, self.room, self.event, "¡¡", self.reply_to, msg, True
            )
