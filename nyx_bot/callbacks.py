import asyncio
import logging

from nio import (
    AsyncClient,
    MatrixRoom,
    PowerLevels,
    RoomGetStateEventError,
    RoomMemberEvent,
    RoomMessageText,
    UnknownEvent,
)

from nyx_bot.bot_commands import Command
from nyx_bot.config import Config
from nyx_bot.message_responses import Message
from nyx_bot.storage import MatrixMessage, MembershipUpdates
from nyx_bot.utils import (
    get_replaces,
    get_reply_to,
    is_bot_event,
    make_datetime,
    should_record_message_content,
    strip_beginning_quote,
)

logger = logging.getLogger(__name__)


class Callbacks:
    def __init__(self, client: AsyncClient, config: Config):
        """
        Args:
            client: nio client used to interact with matrix.

            config: Bot configuration parameters.
        """
        self.client = client
        self.config = config
        self.room_features = config.room_features
        self.command_prefix = config.command_prefix
        self.replace_map = {}

    async def message(self, room: MatrixRoom, event: RoomMessageText) -> None:
        """Callback for when a message event is received

        Args:
            room: The room the event came from.

            event: The event defining the message.
        """
        if event_replace := get_replaces(event):
            self.replace_map[event_replace] = event.event_id

        # Extract the message text
        msg = strip_beginning_quote(event.body)

        # Ignore messages from ourselves
        if event.sender == self.client.user and is_bot_event(event):
            return

        # XXX: Special case for Arch Linux CN
        # Also ignore maubot commands
        if msg.startswith("!"):
            return

        logger.debug(
            f"Bot message received for room {room.display_name} | "
            f"{room.user_name(event.sender)}: {msg}"
        )

        reply_to = get_reply_to(event)
        logger.debug(f"In-Reply-To: {reply_to}")

        # Process as message if in a public room without command prefix
        has_command_prefix = msg.startswith(self.command_prefix)

        # room.is_group is often a DM, but not always.
        # room.is_group does not allow room aliases
        # room.member_count > 2 ... we assume a public room
        # room.member_count <= 2 ... we assume a DM
        if not has_command_prefix and room.member_count > 2:
            include_text = True
            # Record this message.
            if not should_record_message_content(self.room_features, room.room_id):
                include_text = False
            MatrixMessage.update_message(room, event, event_replace, include_text)
            # General message listener
            message = Message(
                self.client, self.config, msg, room, event, reply_to, self.room_features
            )
            asyncio.create_task(message.process())

        # Treat it as a command only if it has a prefix
        if has_command_prefix:
            # Remove the command prefix
            msg = msg[len(self.command_prefix) :]

            command = Command(
                self.client,
                self.config,
                msg,
                room,
                event,
                reply_to,
                self.replace_map,
                self.command_prefix,
            )
            asyncio.create_task(command.process())

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

    async def membership(self, room: MatrixRoom, event: RoomMemberEvent) -> None:
        timestamp = make_datetime(event.server_timestamp)
        MembershipUpdates.update_membership(room, event, timestamp)
        if event.membership == "join" and event.prev_membership in (
            None,
            "invite",
            "leave",
        ):
            content = event.content or {}
            name = content.get("displayname")
            logger.debug(
                f"New user joined in {room.display_name}: {name} ({event.state_key})"
            )
            state_resp = await self.client.room_get_state_event(
                room.room_id, "m.room.power_levels"
            )
            if isinstance(state_resp, RoomGetStateEventError):
                logger.debug(
                    f"Failed to get power level data in room {room.display_name} ({room.room_id}). Stop processing."
                )
                return
            content = state_resp.content
            powers = PowerLevels(
                events=content.get("events"), users=content.get("users")
            )
            if not powers.can_user_send_state(self.client.user, "m.room.power_levels"):
                logger.debug(
                    f"Bot is unable to update power levels in {room.display_name} ({room.room_id}). Stop processing."
                )
