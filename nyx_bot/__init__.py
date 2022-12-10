import asyncio
import logging
import sys

# Check that we're not running on an unsupported Python version.
if sys.version_info < (3, 5):
    print("nyx_bot requires Python 3.5 or above.")
    sys.exit(1)

logger = logging.getLogger(__name__)


def run():
    try:
        from . import main

        # Run the main function of the bot
        asyncio.get_event_loop().run_until_complete(main.main())
    except ImportError as e:
        print("Unable to import nyx_box.main:", e)
    except KeyboardInterrupt:
        logger.info("Bye!")
