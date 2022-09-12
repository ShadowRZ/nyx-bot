import aiohttp
from nio import AsyncClient, MatrixRoom, RoomMessageText

from nyx_bot.chat_functions import send_text_to_room
from nyx_bot.storage import ArchPackage

ARCHLINUXCN_PKGPATH = "https://repo.archlinuxcn.org/x86_64/archlinuxcn.db.tar.gz"


async def send_archlinuxcn_pkg(
    client: AsyncClient,
    room: MatrixRoom,
    event: RoomMessageText,
    pkgname: str,
):
    # Only get the first matching one.
    result = ArchPackage.get_or_none(ArchPackage.name == pkgname)
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
        mtime = result.builddate
        string = f"""\
**Package Info**:

* Name: {result.name}
* Verison: {result.version}
* Build Date: {mtime.isoformat(timespec="seconds")}
* Packager: {result.packager}
* URL: {result.url or "(None)"}
"""
        await send_text_to_room(
            client,
            room.room_id,
            string,
            False,
            True,
            event.event_id,
        )


async def update_archlinuxcn_pkg(
    client: AsyncClient,
    room: MatrixRoom,
    event: RoomMessageText,
):
    async with aiohttp.ClientSession() as session:
        async with session.get(ARCHLINUXCN_PKGPATH) as resp:
            data = await resp.read()
            ArchPackage.populate_from_blob(data, "archlinuxcn")
    await client.room_typing(room.room_id, False)
    await send_text_to_room(
        client,
        room.room_id,
        "Done.",
        notice=False,
        markdown_convert=False,
        reply_to_event_id=event.event_id,
        literal_text=True,
    )
