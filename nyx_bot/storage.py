import logging

from peewee import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    IntegerField,
    Model,
)
from playhouse.db_url import connect

from nyx_bot.config import config

logger = logging.getLogger(__name__)

db = connect(config.database["connection_string"])


class BaseModel(Model):
    class Meta:
        database = db


class MatrixMessage(BaseModel):
    room_id = CharField()
    event_id = CharField()
    origin_server_ts = IntegerField()
    external_url = CharField(null=True)
    sender = CharField()
    replaced_by = CharField(null=True)
    is_replacement = BooleanField(default=False)
    date = DateField()
    datetime = DateTimeField()


db.connect()
db.create_tables([MatrixMessage])
