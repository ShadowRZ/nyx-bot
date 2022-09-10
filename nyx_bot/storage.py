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
