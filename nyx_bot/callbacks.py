import logging
import re
import time

from nio import (
    AsyncClient,
    InviteMemberEvent,
    JoinError,
    MatrixRoom,
    RoomMessageText,
    UnknownEvent,
)

from nyx_bot.bot_commands import Command
from nyx_bot.chat_functions import send_exception, send_jerryxiao
from nyx_bot.config import Config
from nyx_bot.storage import Storage

logger = logging.getLogger(__name__)


class Callbacks:
    def __init__(self, client: AsyncClient, store: Storage, config: Config):
        """
        Args:
            client: nio client used to interact with matrix.

            store: Bot storage.

            config: Bot configuration parameters.
        """
        self.client = client
        self.store = store
        self.config = config
        self.command_prefix = config.command_prefix
        self.replace_map = {}

    async def message(self, room: MatrixRoom, event: RoomMessageText) -> None:
        """Callback for when a message event is received

        Args:
            room: The room the event came from.

            event: The event defining the message.
        """
        # Ignore too old messages
        current_time = int(time.time() * 1000)
        if current_time - event.server_timestamp > 60000:
            return

        # Check if we should replace things.
        content = event.source.get("content")
        relates_to = content.get("m.relates_to") or {}
        rel_type = relates_to.get("rel_type")
        if rel_type == "m.replace":
            event_id = relates_to.get("event_id")
            self.replace_map[event_id] = event.event_id
            logger.debug(f"Replace {event_id} with {event.event_id}")

        # Extract the message text
        msg = event.body

        # Ignore messages from ourselves
        if event.sender == self.client.user:
            return

        logger.debug(
            f"Bot message received for room {room.display_name} | "
            f"{room.user_name(event.sender)}: {msg}"
        )

        reply_to = ((content.get("m.relates_to") or {}).get("m.in_reply_to") or {}).get(
            "event_id"
        )
        logger.debug(f"In-Reply-To: {reply_to}")

        has_jerryxiao_prefix = False
        has_command_prefix = False
        for i in msg.splitlines():
            if re.match("^(!!|\\\\|/|¡¡)", i):
                has_jerryxiao_prefix = True
                msg = i
                break
            elif i.startswith(self.command_prefix):
                has_command_prefix = True
                msg = i
                break

        if has_jerryxiao_prefix and reply_to:
            if msg.startswith("/"):
                await send_jerryxiao(self.client, room, event, "/", reply_to, msg)
            elif msg.startswith("!!"):
                await send_jerryxiao(self.client, room, event, "!!", reply_to, msg)
            elif msg.startswith("\\"):
                await send_jerryxiao(
                    self.client, room, event, "\\", reply_to, msg, True
                )
            elif msg.startswith("¡¡"):
                await send_jerryxiao(
                    self.client, room, event, "¡¡", reply_to, msg, True
                )

        # Treat it as a command only if it has a prefix
        if has_command_prefix:
            # Remove the command prefix
            msg = msg[len(self.command_prefix) :]

            command = Command(
                self.client,
                self.store,
                self.config,
                msg,
                room,
                event,
                reply_to,
                self.replace_map,
            )
            try:
                await command.process()
            except Exception as inst:
                await send_exception(self.client, inst, room.room_id, event.event_id)

    async def unknown(self, room: MatrixRoom, event: UnknownEvent) -> None:
        """Callback for when an event with a type that is unknown to matrix-nio is received.
        Currently this is used for reaction events, which are not yet part of a released
        matrix spec (and are thus unknown to nio).

        Args:
            room: The room the reaction was sent in.

            event: The event itself.
        """
        if event.type == "m.reaction":
            # Get the ID of the event this was a reaction to
            relation_dict = event.source.get("content", {}).get("m.relates_to", {})

            reacted_to = relation_dict.get("event_id")
            if reacted_to and relation_dict.get("rel_type") == "m.annotation":
                return

        logger.debug(
            f"Got unknown event with type to {event.type} from {event.sender} in {room.room_id}."
        )

    async def invite(self, room: MatrixRoom, event: InviteMemberEvent) -> None:
        """Callback for when an invite is received. Join the room specified in the invite.

        Args:
            room: The room that we are invited to.

            event: The invite event.
        """
        logger.debug(f"Got invite to {room.room_id} from {event.sender}.")

        # Attempt to join 3 times before giving up
        for attempt in range(3):
            result = await self.client.join(room.room_id)
            if type(result) == JoinError:
                logger.error(
                    f"Error joining room {room.room_id} (attempt %d): %s",
                    attempt,
                    result.message,
                )
            else:
                break
        else:
            logger.error("Unable to join room: %s", room.room_id)

        # Successfully joined room
        logger.info(f"Joined {room.room_id}")

    async def invite_event_filtered_callback(
        self, room: MatrixRoom, event: InviteMemberEvent
    ) -> None:
        """
        Since the InviteMemberEvent is fired for every m.room.member state received
        in a sync response's `rooms.invite` section, we will receive some that are
        not actually our own invite event (such as the inviter's membership).
        This makes sure we only call `callbacks.invite` with our own invite events.
        """
        if event.state_key == self.client.user_id:
            # This is our own membership (invite) event
            await self.invite(room, event)
