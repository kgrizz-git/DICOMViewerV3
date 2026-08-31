"""Temporary probe used to verify Sourcery's manual-review command."""


def build_probe_values() -> list[int]:
    values = []
    for number in range(3):
        values.append(number)
    return values
