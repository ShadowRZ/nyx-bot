import tarfile
from datetime import datetime
from io import BytesIO
from typing import Optional

from nio import MatrixRoom, RoomMemberEvent, RoomMessageText
from peewee import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
    chunked,
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


class MembershipUpdates(Model):
    room_id = CharField()
    event_id = CharField()
    origin_server_ts = IntegerField()
    sender = CharField()
    state_key = CharField()
    avatar_url = CharField(null=True)
    prev_avatar_url = CharField(null=True)
    name = CharField(null=True)
    prev_name = CharField(null=True)
    date = DateField()
    datetime = DateTimeField()

    @staticmethod
    def update_membership(
        room: MatrixRoom,
        event: RoomMemberEvent,
        timestamp: datetime,
    ):
        content = event.content or {}
        prev_content = event.prev_content or {}
        avatar_url = content.get("avatar_url")
        prev_avatar_url = prev_content.get("avatar_url")
        name = content.get("displayname")
        prev_name = prev_content.get("displayname")
        db_item = MembershipUpdates.get_or_none(
            (MembershipUpdates.room_id == room.room_id)
            & (MembershipUpdates.event_id == event.event_id)
        )
        if not db_item:
            db_item = MembershipUpdates()
        db_item.room_id = room.room_id
        db_item.event_id = event.event_id
        db_item.origin_server_ts = event.server_timestamp
        db_item.sender = event.sender
        db_item.state_key = event.state_key
        db_item.datetime = timestamp
        db_item.date = timestamp.date()
        db_item.avatar_url = avatar_url
        db_item.prev_avatar_url = prev_avatar_url
        db_item.name = name
        db_item.prev_name = prev_name
        db_item.save()


class UserTag(Model):
    room_id = CharField()
    sender = CharField()
    tag = CharField()

    @staticmethod
    def update_user_tag(room_id: str, sender: str, tag: str):
        user_tag = UserTag.get_or_none(
            (UserTag.room_id == room_id) & (UserTag.sender == sender)
        )
        if not user_tag:
            user_tag = UserTag(room_id=room_id, sender=sender)
        user_tag.tag = tag
        user_tag.save()

    @staticmethod
    def delete_user_tag(room_id: str, sender: str):
        UserTag.delete().where(
            (UserTag.room_id == room_id) & (UserTag.sender == sender)
        ).execute()


pkginfo_database = SqliteDatabase(None)


class ArchPackage(Model):
    filename = TextField()
    name = TextField()
    base = TextField(null=True)
    version = TextField()
    desc = TextField()
    url = TextField(null=True)
    arch = TextField()
    packager = TextField()
    builddate = DateTimeField()
    repo = TextField()

    class Meta:
        database = pkginfo_database

    @staticmethod
    def populate_from_blob(blob, repo):
        bytesio = BytesIO(blob)
        tar = tarfile.open("r", fileobj=bytesio)

        parsed_list = []

        for tarinfo in tar:
            if tarinfo.isreg() and tarinfo.name.endswith("/desc"):
                desc_file = tar.extractfile(tarinfo)
                desc = parse_desc(desc_file.read().decode("utf-8"), repo)
                parsed_list.append(desc)

        update_package_info(parsed_list, repo)


def parse_desc(desc, repo):
    lines = desc.splitlines()
    parsed = {}
    key = None
    for line in lines:
        # Key
        if line.startswith("%"):
            key = line
            parsed[line] = []
        # Seperator
        elif line == "":
            continue
        # Values
        else:
            parsed[key].append(line)

    data = {}
    data["filename"] = parsed["%FILENAME%"][0]
    data["name"] = parsed["%NAME%"][0]
    base = parsed.get("%BASE%")
    if base:
        data["base"] = base[0]
    data["version"] = parsed["%VERSION%"][0]
    data["desc"] = parsed["%DESC%"][0]
    url = parsed.get("%URL%")
    if url:
        data["url"] = url[0]
    data["arch"] = parsed["%ARCH%"][0]
    data["packager"] = parsed["%PACKAGER%"][0]
    data["builddate"] = datetime.fromtimestamp(int(parsed["%BUILDDATE%"][0]))
    data["repo"] = repo

    return data


def insert_package_info(data_source, repo):
    with pkginfo_database.atomic():
        for batch in chunked(data_source, 100):
            ArchPackage.insert_many(batch).execute()


def update_package_info(data_source, repo):
    pkgnames = {data["name"] for data in data_source}
    pkgarches = {}
    for data in data_source:
        arches = pkgarches.get(data["name"])
        if arches is None:
            arches = {}
            pkgarches[data["name"]] = arches
        arches[data["arch"]] = data
    with pkginfo_database.atomic():
        # Delete removed packages (in all arches)
        ArchPackage.delete().where(
            (ArchPackage.name.not_in(pkgnames)) & (ArchPackage.repo == repo)
        ).execute()
        should_insert = []
        for pkgname in pkgnames:
            archdatas = pkgarches[pkgname]
            arches = list(archdatas.keys())
            # Delete packages that lost some arches
            ArchPackage.delete().where(
                (ArchPackage.name == pkgname)
                & (ArchPackage.repo == repo)
                & (ArchPackage.arch.not_in(arches))
            ).execute()
            query = ArchPackage.select().where(
                (ArchPackage.name == pkgname) & (ArchPackage.repo == repo)
            )
            if query.count() == 0:
                # New package
                should_insert.extend(archdatas.values())
            else:
                # Update existing packages
                known_arches = set()
                for item in query:
                    archdata = archdatas[item.arch]
                    for k, v in archdata.items():
                        setattr(item, k, v)
                    item.save()
                    known_arches.add(item.arch)
                unknown_arches = set(archdatas.keys()) - known_arches
                for i in unknown_arches:
                    should_insert.extend(archdatas[i])

        for batch in chunked(should_insert, 100):
            ArchPackage.insert_many(batch).execute()
