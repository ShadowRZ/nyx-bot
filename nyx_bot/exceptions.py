class NyxBotValueError(ValueError):
    def __init__(self, reason):
        super().__init__(reason)


class NyxBotRuntimeError(RuntimeError):
    def __init__(self, reason):
        super().__init__(reason)
