# This file holds custom error types that you can define for your application.


class ConfigError(RuntimeError):
    """An error encountered during reading the config file.

    Args:
        msg: The message displayed to the user on error.
    """

    def __init__(self, msg: str):
        super(ConfigError, self).__init__("%s" % (msg,))


class NyxBotValueError(ValueError):
    def __init__(self, reason):
        super().__init__(reason)


class NyxBotRuntimeError(RuntimeError):
    def __init__(self, reason):
        super().__init__(reason)
