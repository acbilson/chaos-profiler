from . import letters
from . import numbers


def get_letters_and_numbers() -> tuple[list[str], list[int]]:
    return (letters.get_letters(), numbers.get_numbers())
