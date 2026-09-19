"""User roles used across the application."""

from enum import Enum


class Role(str, Enum):
    """Controlled set of user roles. Never trust roles from the frontend."""

    admin = "admin"
    operator = "operator"
    viewer = "viewer"