"""Custom exception types for the toolkit.

Why custom exceptions?
    The CLI needs to tell apart two kinds of failure:

    * A *user* mistake (bad input text, an invalid mapping). The program
      should show a friendly message and keep running.
    * A *programmer* mistake (a bug). The program should crash loudly so
      the bug is noticed and fixed.

    Every user-facing error inherits from ``ToolkitError``, so the CLI can
    write ``except ToolkitError`` and catch exactly the first kind while
    letting genuine bugs through.
"""


class ToolkitError(Exception):
    """Base class for every error that should be shown to the user."""


class ParseError(ToolkitError):
    """The text typed by the user could not be understood."""


class InvalidFunctionError(ToolkitError):
    """A mapping does not satisfy the definition of a function f: A -> B.

    A mapping can break several rules at once (for example, one input is
    missing AND another output is outside the codomain). Instead of
    stopping at the first problem, we collect all of them in
    ``self.problems`` so the user can fix everything in one attempt.
    """

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))
