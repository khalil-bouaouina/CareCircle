"""Authentication, session token creation, and circle membership services (business logic)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from .. import config
from ..models import Elder, Person, UserAccount, UserElderLink
from ..repositories import accounts, people


# --- password hashing (standard PBKDF2-HMAC-SHA256) --------------------------


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${key.hex()}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        salt, key_hex = password_hash.split("$", 1)
        expected = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return hmac.compare_digest(key_hex, expected.hex())
    except (ValueError, AttributeError):
        return False


# --- signed session tokens ----------------------------------------------------


def create_session_token(payload: dict[str, Any]) -> str:
    """Encode payload as base64 and sign with HMAC-SHA256."""
    payload_with_ts = dict(payload)
    payload_with_ts["_ts"] = int(time.time())
    raw_json = json.dumps(payload_with_ts, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_json).decode("ascii").rstrip("=")
    sig = hmac.new(config.SESSION_SECRET_KEY.encode("utf-8"), b64_payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"


def decode_session_token(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    b64_payload, sig = token.rsplit(".", 1)
    expected_sig = hmac.new(
        config.SESSION_SECRET_KEY.encode("utf-8"), b64_payload.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        # Add padding back if necessary
        padded = b64_payload + "=" * (-len(b64_payload) % 4)
        raw_json = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        data = json.loads(raw_json)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


# --- user registration & authentication ---------------------------------------


def authenticate_user(email: str, password: str) -> UserAccount | None:
    user = accounts.get_user_by_email(email)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def register_caregiver(
    name: str,
    email: str,
    password: str,
    elder_name: str | None = None,
    capacity_mode: str = "assisted",
    language: str = "fr",
) -> tuple[UserAccount, Elder | None]:
    name = name.strip()
    email = email.strip().lower()
    if not name:
        raise ValueError("Le nom est obligatoire")
    if "@" not in email or "." not in email:
        raise ValueError("Adresse email invalide")
    if len(password) < 6:
        raise ValueError("Le mot de passe doit comporter au moins 6 caractères")

    existing = accounts.get_user_by_email(email)
    if existing is not None:
        raise ValueError("Un compte existe déjà avec cette adresse email")

    user_id = accounts.create_user(email, hash_password(password), name)
    user = accounts.get_user_by_id(user_id)
    if user is None:
        raise RuntimeError("Impossible de créer le compte")

    elder: Elder | None = None
    if elder_name and elder_name.strip():
        elder_id = people.create_elder(None, elder_name.strip(), language, capacity_mode)
        person_id = people.create_person(None, elder_id, name, "primary_caregiver", language)
        accounts.link_user_to_elder(user.id, elder_id, person_id, "primary_caregiver")
        elder = people.get_elder(elder_id)

    return user, elder


def create_elder_for_user(
    user_id: int,
    display_name: str,
    capacity_mode: str = "assisted",
    primary_language: str = "fr",
) -> tuple[Elder, Person]:
    user = accounts.get_user_by_id(user_id)
    if user is None:
        raise ValueError("Utilisateur introuvable")

    elder_id = people.create_elder(None, display_name.strip(), primary_language, capacity_mode)
    person_id = people.create_person(None, elder_id, user.name, "primary_caregiver", primary_language)
    accounts.link_user_to_elder(user_id, elder_id, person_id, "primary_caregiver")
    elder = people.get_elder(elder_id)
    person = people.get_person(person_id)
    if elder is None or person is None:
        raise RuntimeError("Erreur lors de la création du dossier de l'aîné")
    return elder, person


def add_family_member(
    elder_id: int,
    name: str,
    email: str,
    password: str,
    role: str = "family",
    language: str = "fr",
) -> tuple[UserAccount, Person]:
    name = name.strip()
    email = email.strip().lower()
    if not name or "@" not in email:
        raise ValueError("Nom et email requis")
    if len(password) < 6:
        raise ValueError("Mot de passe d'au moins 6 caractères")

    user = accounts.get_user_by_email(email)
    if user is None:
        user_id = accounts.create_user(email, hash_password(password), name)
        user = accounts.get_user_by_id(user_id)
        if user is None:
            raise RuntimeError("Erreur création compte")

    if role == "elder":
        accounts.link_user_to_elder(user.id, elder_id, None, "elder")
        return user, None

    person_id = people.create_person(None, elder_id, name, role, language)
    person = people.get_person(person_id)
    if person is None:
        raise RuntimeError("Erreur création profil")

    accounts.link_user_to_elder(user.id, elder_id, person_id, role)
    return user, person


def register_elder(
    name: str,
    email: str,
    password: str,
    capacity_mode: str = "self",
    language: str = "fr",
) -> tuple[UserAccount, Elder]:
    name = name.strip()
    email = email.strip().lower()
    if not name:
        raise ValueError("Le nom est obligatoire")
    if "@" not in email or "." not in email:
        raise ValueError("Adresse email invalide")
    if len(password) < 6:
        raise ValueError("Le mot de passe doit comporter au moins 6 caractères")

    existing = accounts.get_user_by_email(email)
    if existing is not None:
        raise ValueError("Un compte existe déjà avec cette adresse email")

    user_id = accounts.create_user(email, hash_password(password), name)
    user = accounts.get_user_by_id(user_id)
    if user is None:
        raise RuntimeError("Impossible de créer le compte")

    elder_id = people.create_elder(None, name, language, capacity_mode)
    accounts.link_user_to_elder(user.id, elder_id, None, "elder")
    elder = people.get_elder(elder_id)
    if elder is None:
        raise RuntimeError("Erreur création dossier aîné")

    return user, elder


