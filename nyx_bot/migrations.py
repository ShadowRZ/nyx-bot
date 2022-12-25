# Used for migrations
import logging

from peewee import PostgresqlDatabase, SqliteDatabase
from playhouse.migrate import PostgresqlMigrator, SqliteMigrator, migrate

from nyx_bot.storage import DatabaseVersion, MatrixMessage, UserTag

logger = logging.getLogger(__name__)


def migrate_db(db):
    if isinstance(db, SqliteDatabase):
        migrator = SqliteMigrator(db)
    elif isinstance(db, PostgresqlDatabase):
        migrator = PostgresqlMigrator(db)

    version_item = DatabaseVersion.get_or_none()
    if version_item is None:
        version_item = DatabaseVersion()
        version_item.version = 3
        version_item.save()
        return

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

    version_item.version = 3
    version_item.save()
