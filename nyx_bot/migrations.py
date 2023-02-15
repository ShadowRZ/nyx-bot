# Used for migrations
import logging

from peewee import BigIntegerField, MySQLDatabase, PostgresqlDatabase, SqliteDatabase
from playhouse.migrate import MySQLMigrator, PostgresqlMigrator, SqliteMigrator, migrate

from nyx_bot.storage import DatabaseVersion, MatrixMessage, UserTag

logger = logging.getLogger(__name__)


def migrate_db(db):
    version_item = DatabaseVersion.get_or_none()
    if version_item is None:
        version_item = DatabaseVersion()
        version_item.version = 4
        version_item.save()
        return

    if isinstance(db, SqliteDatabase):
        migrator = SqliteMigrator(db)
    elif isinstance(db, PostgresqlDatabase):
        migrator = PostgresqlMigrator(db)
    elif isinstance(db, MySQLDatabase):
        migrator = MySQLMigrator(db)

    logger.info(f"Database version: {version_item.version}")
    if version_item.version == 1:
        migrate(migrator.add_column("usertag", "locked", UserTag.locked))
    elif version_item.version == 2:
        migrate(migrator.add_column("matrixmessage", "body", MatrixMessage.body))
        migrate(
            migrator.add_column(
                "matrixmessage", "formatted_body", MatrixMessage.formatted_body
            )
        )
    elif version_item.version == 3:
        migrate(
            migrator.alter_column_type(
                "matrixmessage", "origin_server_ts", BigIntegerField
            )
        )
        migrate(
            migrator.alter_column_type(
                "membershipupdates", "origin_server_ts", BigIntegerField
            )
        )

    version_item.version = 4
    version_item.save()
