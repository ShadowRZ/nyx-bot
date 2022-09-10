from peewee import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    IntegerField,
    Model,
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
