"""Centralizovana konfiguracija uloga i privilegija.

Tri uloge u sistemu:
  - citizen  : podnosi zahtjeve, vidi svoje predmete
  - officer  : obrađuje predmete koji su mu dodijeljeni
  - admin    : sve gore + KPI dashboard, bulk akcije, upravljanje službenicima

Efektivna uloga = uloga iz baze ili `admin` ako je korisnik u APP_ADMIN_USERS env listi.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Set

from database.database import get_user_role, is_user_admin


DEFAULT_ADMIN_USERS = "admin,rapoz"


class Role(str, Enum):
    CITIZEN = "citizen"
    OFFICER = "officer"
    ADMIN = "admin"


def get_env_admin_users() -> Set[str]:
    raw = os.getenv("APP_ADMIN_USERS", DEFAULT_ADMIN_USERS)
    return {item.strip() for item in raw.split(",") if item.strip()}


def get_effective_role(username: str) -> Role:
    """Vraća efektivnu ulogu uzimajući u obzir env override."""
    if not username:
        return Role.CITIZEN

    if username in get_env_admin_users():
        return Role.ADMIN

    role = (get_user_role(username) or "citizen").lower()
    if role == "admin":
        return Role.ADMIN
    if role == "officer":
        return Role.OFFICER
    return Role.CITIZEN


def is_admin(username: str) -> bool:
    return get_effective_role(username) == Role.ADMIN


def is_officer(username: str) -> bool:
    return get_effective_role(username) == Role.OFFICER


def is_staff(username: str) -> bool:
    """Da li ima pristup admin/officer panel-u (officer ili admin)."""
    return get_effective_role(username) in {Role.OFFICER, Role.ADMIN}


def has_admin_access(username: str) -> bool:
    """Backwards-compat sa starom `is_admin_user` logikom (officer + admin)."""
    return is_staff(username) or is_user_admin(username)
