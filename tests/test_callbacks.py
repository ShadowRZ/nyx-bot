import unittest
from unittest.mock import Mock

import nio

from nyx_bot.callbacks import Callbacks


class CallbacksTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Create a Callbacks object and give it some Mock'd objects to use
        self.fake_client = Mock(spec=nio.AsyncClient)
        self.fake_client.user = "@fake_user:example.com"

        # We don't spec config, as it doesn't currently have well defined attributes
        self.fake_config = Mock()

        self.callbacks = Callbacks(self.fake_client, self.fake_config)


if __name__ == "__main__":
    unittest.main()
