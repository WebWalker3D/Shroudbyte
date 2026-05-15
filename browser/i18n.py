"""Minimal i18n scaffolding for Shroudbyte.

We don't yet ship translation catalogs — every string is currently
English. This module exists so new code can wrap user-visible strings
in ``_(...)`` from day one, and existing code can be migrated string
by string without breaking anything.

Once we have a ``locale/`` directory populated with .mo files, this
module will start returning translated text. Until then, ``_`` is the
identity function plus a hook for printf-style format substitution.

Usage::

    from browser.i18n import _

    box.setText(_("Shroudbyte didn't close cleanly last time."))
    status.showMessage(_("Imported %(n)d new bookmarks") % {"n": count})

Translators: to start a new catalog, run ``scripts/extract-i18n.sh``
which produces ``locale/shroudbyte.pot``.
"""

from __future__ import annotations

import gettext
import os
from pathlib import Path


_DOMAIN = "shroudbyte"

# Resolve locale dir relative to the installed package. If a system
# install put translations under /usr/share/locale, gettext will fall
# back to that automatically when our local dir is missing.
_PACKAGE_DIR = Path(__file__).resolve().parent
_LOCALE_DIR = _PACKAGE_DIR.parent / "locale"

_translation: gettext.NullTranslations | None = None


def _install_translation() -> gettext.NullTranslations:
    """Pick a translation based on the current LANG/LC_ALL env vars."""
    if _LOCALE_DIR.is_dir():
        try:
            return gettext.translation(
                _DOMAIN, localedir=str(_LOCALE_DIR), fallback=True
            )
        except OSError:
            pass
    # No locale dir / no matching catalog — gettext.NullTranslations is
    # the identity function, which is what we want until catalogs exist.
    return gettext.NullTranslations()


def _get_translation() -> gettext.NullTranslations:
    global _translation
    if _translation is None:
        _translation = _install_translation()
    return _translation


def gettext_(message: str) -> str:
    """Translate ``message`` if a catalog matches; else return as-is."""
    return _get_translation().gettext(message)


# Conventional alias so call sites read like every other gettext-using
# Python project. Bound at import time so it's cheap to call.
_ = gettext_


def set_language(lang_code: str | None):
    """Override the autodetected language (e.g. for a settings toggle).

    Pass ``None`` to revert to the env-var-driven default.
    """
    global _translation
    if not lang_code:
        _translation = None
        return
    if _LOCALE_DIR.is_dir():
        try:
            _translation = gettext.translation(
                _DOMAIN,
                localedir=str(_LOCALE_DIR),
                languages=[lang_code],
                fallback=True,
            )
            return
        except OSError:
            pass
    _translation = gettext.NullTranslations()


def available_languages() -> list[str]:
    """Return language codes for which we have a .mo file shipped."""
    if not _LOCALE_DIR.is_dir():
        return []
    langs = []
    for child in _LOCALE_DIR.iterdir():
        if (child / "LC_MESSAGES" / f"{_DOMAIN}.mo").exists():
            langs.append(child.name)
    return sorted(langs)
