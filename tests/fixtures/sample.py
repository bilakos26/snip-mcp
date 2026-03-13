"""Sample Python module for testing symbol extraction."""

CONSTANT_VALUE = 42


class MyClass:
    """A sample class for testing."""

    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> str:
        """Return a greeting string."""
        return f"Hello, {self.name}!"

    @staticmethod
    def static_method() -> int:
        return 1


def top_level_function(x: int, y: int) -> int:
    """Add two numbers together."""
    return x + y


@property
def decorated_func():
    pass
