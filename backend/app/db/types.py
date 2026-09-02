"""Reusable column types."""

from enum import StrEnum

import sqlalchemy as sa


def enum_col(enum_cls: type[StrEnum], name: str) -> sa.Enum:
    """A StrEnum stored as VARCHAR with a named CHECK constraint.

    `native_enum=False` avoids creating a PostgreSQL ENUM type; the allowed
    values are enforced by `ck_<table>_<name>` instead.
    """
    return sa.Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda cls: [member.value for member in cls],
    )
