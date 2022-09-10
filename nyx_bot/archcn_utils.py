from datetime import datetime

from nio import AsyncClient, MatrixRoom, RoomMessageText

from nyx_bot.chat_functions import send_text_to_room
from nyx_bot.storage import Pkginfo


async def send_archlinuxcn_pkg(
    client: AsyncClient,
    room: MatrixRoom,
    event: RoomMessageText,
    pkgname: str,
):
    # Only get the first matching one.
    result = Pkginfo.get_or_none(Pkginfo.pkgname == pkgname)
    if result is None:
        await send_text_to_room(
            client,
            room.room_id,
            f"No package called {pkgname} in [archlinuxcn].",
            False,
            False,
            event.event_id,
            True,
        )
    else:
        # Get it.
        mtime = datetime.fromtimestamp(result.mtime)
        string = f"""\
**Package Info**:

* Name: {result.pkgname}
* Verison {result.pkgver}
* Update Time: {mtime.isoformat(timespec="seconds")}
* Owner: {result.owner}
"""
        await send_text_to_room(
            client,
            room.room_id,
            string,
            False,
            True,
            event.event_id,
        )
