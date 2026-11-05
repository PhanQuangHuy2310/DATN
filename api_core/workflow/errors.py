"""Command errors shared by workflow services and integrations."""


class CommandError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        status: int = 400,
        fields: dict[str, list[str]] | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.status = status
        self.fields = fields
