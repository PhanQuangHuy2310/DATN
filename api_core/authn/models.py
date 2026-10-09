from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthUser:
    id: str
    username: str
    display_name: str
    department_id: str
    password_hash: str
    auth_version: int
    is_active: bool
    must_change_password: bool


@dataclass(frozen=True)
class Actor:
    id: str
    username: str
    display_name: str
    department_id: str
    auth_version: int
    roles: frozenset[str]
    must_change_password: bool
