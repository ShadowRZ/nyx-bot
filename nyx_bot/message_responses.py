import logging
import re
from zlib import crc32

from nio import AsyncClient, MatrixRoom, RoomMessageText

from nyx_bot.chat_functions import (
    gen_result_randomdraw,
    send_exception,
    send_text_to_room,
)
from nyx_bot.config import Config
from nyx_bot.jerryxiao import send_jerryxiao
from nyx_bot.trpg_dicer import get_trpg_dice_result
from nyx_bot.utils import should_enable_jerryxiao, should_enable_randomdraw

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
        room_features,
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
        self.room_features = room_features

    async def process(self) -> None:
        """Process and possibly respond to the message"""
        try:
            await self._process()
        except Exception as inst:
            # Clear any previous typing event
            await self.client.room_typing(self.room.room_id, False)
            await send_exception(
                self.client, inst, self.room.room_id, self.event.event_id
            )

    async def _process(self) -> None:
        if re.match("^(!!|\\\\|/|¡¡)", self.message_content):
            await self._jerryxiao()
        elif self.message_content.startswith("@@"):
            query = self.message_content[2:]
            await self._randomdraw(query, False)
        elif self.message_content.startswith("@%"):
            query = self.message_content[2:]
            await self._randomdraw(query, True)
        elif self.message_content.startswith("@="):
            query = self.message_content[2:]
            await self._trpg_dicer(query)

    async def _randomdraw(self, query: str, prob: bool) -> None:
        if not should_enable_randomdraw(self.room_features, self.room.room_id):
            return
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

    async def _trpg_dicer(self, query: str) -> None:
        msg = get_trpg_dice_result(query.strip())
        await send_text_to_room(
            self.client,
            self.room.room_id,
            str(msg),
            notice=False,
            markdown_convert=False,
            reply_to_event_id=self.event.event_id,
            literal_text=True,
        )

    async def _jerryxiao(self) -> None:
        """Performs features similar to the bot created by Jerry Xiao"""
        if not should_enable_jerryxiao(self.room_features, self.room.room_id):
            return
        msg = self.message_content

        # If the first part of the message is pure ASCII, skip it
        if msg.split()[0].isascii():
            return

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
