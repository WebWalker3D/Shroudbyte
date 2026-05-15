"""Address book — saved contact profiles for form autofill.

A user has zero or more named "addresses", each containing standard
HTML autocomplete fields (name, organization, street, postal code,
etc.). The injected fill JavaScript uses each input's
``autocomplete=""`` attribute to decide which saved value to write.

Storage is plain JSON in DATA_DIR for now. Addresses are PII but not
credentials; tightening this to a vault-encrypted file is tracked as
follow-up work — see [[feature-address-autofill-vault]].
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field

from . import storage


_ADDRESS_FILE = "addresses.json"


# HTML autocomplete tokens we know how to round-trip. The keys here match
# what `<input autocomplete="...">` uses, per the WHATWG spec.
# https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#autofill
AUTOCOMPLETE_FIELDS = (
    "name",            # full name
    "given-name",
    "family-name",
    "organization",
    "street-address",
    "address-line1",
    "address-line2",
    "address-level1",  # state/province
    "address-level2",  # city
    "postal-code",
    "country",
    "country-name",
    "email",
    "tel",
)


@dataclass
class Address:
    """A saved address profile."""

    id: str
    label: str  # user-chosen name like "Home" or "Work"
    fields: dict = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0


def _load_all() -> list[dict]:
    return storage._load_json(_ADDRESS_FILE, [])


def _save_all(entries: list[dict]):
    storage._save_json(_ADDRESS_FILE, entries)


def list_addresses() -> list[Address]:
    """Return every saved address, most recently updated first."""
    raw = _load_all()
    addrs = [Address(**r) for r in raw]
    addrs.sort(key=lambda a: a.updated_at, reverse=True)
    return addrs


def get_address(address_id: str) -> Address | None:
    for entry in _load_all():
        if entry.get("id") == address_id:
            return Address(**entry)
    return None


def add_address(label: str, fields: dict) -> Address:
    """Create a new address with the given label and field map."""
    now = time.time()
    addr = Address(
        id=str(uuid.uuid4()),
        label=label or "Untitled",
        fields=_sanitize_fields(fields),
        created_at=now,
        updated_at=now,
    )
    entries = _load_all()
    entries.append(asdict(addr))
    _save_all(entries)
    return addr


def update_address(address_id: str, label: str | None = None,
                   fields: dict | None = None) -> bool:
    """Update label and/or fields on an existing address."""
    entries = _load_all()
    for entry in entries:
        if entry.get("id") != address_id:
            continue
        if label is not None:
            entry["label"] = label or "Untitled"
        if fields is not None:
            entry["fields"] = _sanitize_fields(fields)
        entry["updated_at"] = time.time()
        _save_all(entries)
        return True
    return False


def remove_address(address_id: str) -> bool:
    entries = _load_all()
    new_entries = [e for e in entries if e.get("id") != address_id]
    if len(new_entries) == len(entries):
        return False
    _save_all(new_entries)
    return True


def _sanitize_fields(fields: dict) -> dict:
    """Keep only known autocomplete tokens with string values."""
    return {
        key: str(value).strip()
        for key, value in (fields or {}).items()
        if key in AUTOCOMPLETE_FIELDS and value is not None
        and str(value).strip()
    }
