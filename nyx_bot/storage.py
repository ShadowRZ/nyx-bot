from typing import Optional

from nio import MatrixRoom, RoomMessageText, Event
from peewee import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)


class MatrixMessage(Model):
    room_id = CharField()
    event_id = CharField()
    origin_server_ts = IntegerField()
    external_url = CharField(null=True)
    sender = CharField()
    replaced_by = CharField(null=True)
    is_replacement = BooleanField(default=False)
    date = DateField()
    datetime = DateTimeField()

    class Meta:
        database = None

    @staticmethod
    def update_message(
        room: MatrixRoom,
        event: RoomMessageText,
        external_url: Optional[str],
        timestamp: datetime,
        event_replace: Optional[str] = None,
    ):
        message_db_item = MatrixMessage.get_or_none(
            (MatrixMessage.room_id == room.room_id)
            & (MatrixMessage.event_id == event.event_id)
        )
        if not message_db_item:
            message_db_item = MatrixMessage()
        message_db_item.room_id = room.room_id
        message_db_item.event_id = event.event_id
        message_db_item.origin_server_ts = event.server_timestamp
        message_db_item.external_url = external_url
        message_db_item.sender = event.sender
        message_db_item.datetime = timestamp
        message_db_item.date = timestamp.date()
        if event_replace:
            message_db_item.is_replacement = True
            replace_item = MatrixMessage.get_or_none(
                (MatrixMessage.room_id == room.room_id)
                & (MatrixMessage.event_id == event_replace)
            )
            if replace_item:
                replace_item.replaced_by = event.event_id
                replace_item.save()
        message_db_item.save()


pkginfo_database = SqliteDatabase(None)


class PkginfoModel(Model):
    class Meta:
        database = pkginfo_database


class Pkginfo(PkginfoModel):
    filename = TextField(null=True, unique=True)
    forarch = TextField(null=True)
    info = TextField(null=True)
    mtime = IntegerField(null=True)
    owner = TextField(null=True)
    pkgarch = TextField(null=True)
    pkgname = TextField(null=True)
    pkgrepo = TextField(null=True)
    pkgver = TextField(null=True)
    state = IntegerField(null=True)

    class Meta:
        table_name = "pkginfo"
        primary_key = False


class Sigfiles(PkginfoModel):
    filename = TextField(null=True, unique=True)
    pkgrepo = TextField(null=True)

    class Meta:
        table_name = "sigfiles"
        primary_key = False


class VersionInfo(PkginfoModel):
    ver = TextField(null=True)

    class Meta:
        table_name = "version_info"
        primary_key = False
