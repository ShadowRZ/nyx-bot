# Used for migrations
from peewee import PostgresqlDatabase, SqliteDatabase
from playhouse.migrate import PostgresqlMigrator, SqliteMigrator, migrate

from nyx_bot.storage import DatabaseVersion, UserTag


def migrate_db(db):
    if isinstance(db, SqliteDatabase):
        migrator = SqliteMigrator(db)
    elif isinstance(db, PostgresqlDatabase):
        migrator = PostgresqlMigrator(db)

    version_item = DatabaseVersion.get_or_none()
    if version_item is None:
        version_item = DatabaseVersion()
        version_item.version = 0
    match version_item.version:
        case 1:
            migrate(migrator.add_column("usertag", "locked", UserTag.locked))

    version_item.version = 2
    version_item.save()
