import asyncio
import logging

from nio import (
    AsyncClient,
    MatrixRoom,
    PowerLevels,
    RoomGetEventError,
    RoomGetStateEventError,
    RoomMemberEvent,
    RoomMessageText,
    RoomPutStateError,
    UnknownEvent,
)

from nyx_bot.bot_commands import Command
from nyx_bot.chat_functions import send_text_to_room
from nyx_bot.config import Config
from nyx_bot.message_responses import Message
from nyx_bot.storage import MatrixMessage, MembershipUpdates
from nyx_bot.utils import (
    get_bot_event_type,
    get_replaces,
    get_reply_to,
    hash_user_id,
    is_bot_event,
    make_datetime,
    should_enable_join_confirm,
    should_record_message_content,
    strip_beginning_quote,
    user_name,
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
            await asyncio.create_task(message.process())

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
            await asyncio.create_task(command.process())

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
                await self._reaction(room, event, reacted_to)
                return

        logger.debug(
            f"Got unknown event with type to {event.type} from {event.sender} in {room.room_id}."
        )

    async def _reaction(
        self, room: MatrixRoom, event: UnknownEvent, reacted_to_id: str
    ) -> None:
        """A reaction was sent to one of our messages. Let's send a reply acknowledging it.

        Args:
            room: The room the reaction was sent in.

            event: The reaction event.

            reacted_to_id: The event ID that the reaction points to.
        """
        logger.debug(f"Got reaction to {room.room_id} from {event.sender}.")

        # Get the original event that was reacted to
        event_response = await self.client.room_get_event(room.room_id, reacted_to_id)
        if isinstance(event_response, RoomGetEventError):
            logger.warning(
                "Error getting event that was reacted to (%s)", reacted_to_id
            )
            return
        reacted_to_event = event_response.event
        if (
            is_bot_event(reacted_to_event)
            and get_bot_event_type(reacted_to_event) == "join_confirm"
        ):
            content = reacted_to_event.source.get("content")
            state_key = content.get("io.github.shadowrz.nyx_bot", {}).get("state_key")
            required_reaction = hash_user_id(state_key)

            reaction_content = (
                event.source.get("content", {}).get("m.relates_to", {}).get("key")
            )

            if reaction_content == required_reaction:
                state_resp = await self.client.room_get_state_event(
                    room.room_id, "m.room.power_levels"
                )
                if isinstance(state_resp, RoomGetStateEventError):
                    logger.debug(
                        f"Failed to get power level data in room {room.display_name} ({room.room_id}). Stop processing."
                    )
                    return
                content = state_resp.content
                events = content.get("events")
                users = content.get("users")
                del users[state_key]
                await self.client.room_put_state(
                    room.room_id,
                    "m.room.power_levels",
                    {"events": events, "users": users},
                )

    async def membership(self, room: MatrixRoom, event: RoomMemberEvent) -> None:
        timestamp = make_datetime(event.server_timestamp)
        MembershipUpdates.update_membership(room, event, timestamp)
        if event.membership == "join" and event.prev_membership in (
            None,
            "invite",
            "leave",
        ):
            if not should_enable_join_confirm(self.room_features, room.room_id):
                return
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
            events = content.get("events")
            events["m.reaction"] = -1
            users = content.get("users")
            powers = PowerLevels(events=events, users=users)
            if not powers.can_user_send_state(self.client.user, "m.room.power_levels"):
                logger.debug(
                    f"Bot is unable to update power levels in {room.display_name} ({room.room_id}). Stop processing."
                )
                return
            users[event.state_key] = -1
            put_state_resp = await self.client.room_put_state(
                room.room_id, "m.room.power_levels", {"events": events, "users": users}
            )
            if isinstance(put_state_resp, RoomPutStateError):
                logger.warn(
                    f"Failed to reconfigure power level: {put_state_resp.message}"
                )
                return
            await send_text_to_room(
                self.client,
                room.room_id,
                f"新加群的用户 {user_name(room, event.state_key)} ({event.state_key}) 请用 Reaction {hash_user_id(event.state_key)} 回复本条消息",
                notice=True,
                markdown_convert=False,
                literal_text=True,
                extended_data={"type": "join_confirm", "state_key": event.state_key},
            )
