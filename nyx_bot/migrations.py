# Used for migrations
from peewee import PostgresqlDatabase, SqliteDatabase
from playhouse.migrate import PostgresqlMigrator, SqliteMigrator, migrate

from nyx_bot.storage import UserTag


def migrate_db(db):
    if isinstance(db, SqliteDatabase):
        migrator = SqliteMigrator(db)
    elif isinstance(db, PostgresqlDatabase):
        migrator = PostgresqlMigrator(db)

    migrate(migrator.add_column("usertag", "locked", UserTag.locked))
