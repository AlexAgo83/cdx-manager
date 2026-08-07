class CdxError(Exception):
    def __init__(self, message, exit_code=1):
        super().__init__(message)
        self.exit_code = exit_code


class CdxArgumentError(CdxError):
    """A usage failure that names its own machine-readable code and arguments.

    Programmatic callers used to get a single `invalid_request` code carrying the
    whole human usage line, which made a missing `--cwd` indistinguishable from
    passing a session name and `--provider` together. Raising this instead lets
    the JSON payload report `code` plus the offending `arguments` as data, so a
    caller never has to match on message text.
    """

    def __init__(self, message, *, code, arguments=(), allowed=None, exit_code=1):
        super().__init__(message, exit_code)
        self.code = code
        self.arguments = tuple(arguments)
        self.allowed = tuple(allowed) if allowed is not None else None
