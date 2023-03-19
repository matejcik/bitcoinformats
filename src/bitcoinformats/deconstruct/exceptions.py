class DeconstructError(Exception):
    pass


class UnsupportedError(DeconstructError):
    pass


class ParseError(DeconstructError):
    pass


class EndOfStream(ParseError):
    pass


class BuildError(DeconstructError):
    pass


class SizeofError(DeconstructError):
    pass


__all__ = [
    "DeconstructError",
    "UnsupportedError",
    "ParseError",
    "EndOfStream",
    "BuildError",
    "SizeofError",
]
