"""IPC handlers for messages sent from injected JavaScript.

Pages run injected scripts (Link Intelligence, Privacy Dashboard, the
PWA detector, etc.) that talk back to Python by emitting console
messages of the form ``__SHROUD_<CHANNEL>__:<payload>``. This module
turns those strings into method calls on the MainWindow.

Decoupling the dispatch table from ``browser.webview`` keeps that file
focused on Qt subclassing and makes the IPC surface testable against
plain stubs — see ``tests/test_webview_ipc.py``.
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Iterable


logger = logging.getLogger("shroudbyte.webview")


# ---------------------------------------------------------------------------
# Prefix constants. The injected JS in scheme.py / annoyance_shield.py /
# fingerprint.py / link_intel.py emits these verbatim; keep them in sync.
# ---------------------------------------------------------------------------

CRED_ALERT_PREFIX     = "__SHROUD_CRED_CAPTURE__:"
PW_FOUND_ALERT        = "__SHROUD_PW_FIELDS_FOUND__"
LINK_HOVER_PREFIX     = "__SHROUD_LINK_HOVER__:"
PRIVACY_ACTION_PREFIX = "__SHROUD_PRIVACY__:"
WATCH_ACTION_PREFIX   = "__SHROUD_WATCH__:"
SETTINGS_ACTION_PREFIX = "__SHROUD_SETTINGS__:"
PAGE_ACT_PREFIX       = "__SHROUD_PAGE_ACT__:"
FORM_DRAFT_PREFIX     = "__SHROUD_FORM_DRAFT__:"
CLIP_PREFIX           = "__SHROUD_CLIP__:"
PWA_PREFIX            = "__SHROUD_PWA__:"
SW_REGISTER_PREFIX    = "__SHROUD_SW_REGISTER__:"
PUSH_SUB_PREFIX       = "__SHROUD_PUSH_SUB__:"
PERM_LEDGER_PREFIX    = "__SHROUD_PERM_LEDGER__:"


# ---------------------------------------------------------------------------
# Handler functions.
#
# Each handler takes (page, mw, payload). ``page`` is the page-like object
# the message arrived on (must expose ``_view_ref`` and ``url()``); ``mw``
# is the MainWindow with the actual feature mixins; ``payload`` is the
# pre-parsed JSON object (or raw string for the clipboard channel).
# ---------------------------------------------------------------------------

def link_hover(page, mw, data):
    href = data.get("href", "")
    if href and hasattr(mw, "_handle_link_hover"):
        mw._handle_link_hover(href, page._view_ref)


def privacy(page, mw, data):
    if hasattr(mw, "_handle_privacy_action"):
        mw._handle_privacy_action(data)


def watch(page, mw, data):
    if hasattr(mw, "_handle_watch_action"):
        mw._handle_watch_action(data)


def settings(page, mw, data):
    if hasattr(mw, "_handle_settings_action"):
        mw._handle_settings_action(data, page._view_ref)


def page_action(page, mw, data):
    if hasattr(mw, "_handle_page_action"):
        mw._handle_page_action(data)


def perm_ledger(page, mw, data):
    if hasattr(mw, "_handle_perm_ledger_action"):
        mw._handle_perm_ledger_action(data)


def form_draft(page, mw, data):
    if hasattr(mw, "_handle_form_draft"):
        mw._handle_form_draft(data)


def pwa(page, mw, data):
    if hasattr(mw, "_handle_pwa"):
        mw._handle_pwa(data)


def sw_register(page, mw, data):
    if hasattr(mw, "_bg_activity"):
        mw._bg_activity.register_service_worker(
            data.get("host", ""), data.get("scope", ""))


def push_sub(page, mw, data):
    if hasattr(mw, "_bg_activity"):
        mw._bg_activity.register_push_subscription(
            data.get("host", ""), data.get("endpoint", ""))


def clipboard(page, mw, text):
    # Clipboard payload is raw text, not JSON.
    if text and hasattr(mw, "_clipboard_history"):
        url = page.url().toString() if page._view_ref else ""
        mw._clipboard_history.record(text, url)


# ---------------------------------------------------------------------------
# Dispatch table — (prefix, label-for-logging, handler, parses_json).
# ---------------------------------------------------------------------------

IPC_HANDLERS: Iterable[tuple[str, str, Callable, bool]] = (
    (LINK_HOVER_PREFIX,      "link-hover",        link_hover,   True),
    (PRIVACY_ACTION_PREFIX,  "privacy",           privacy,      True),
    (WATCH_ACTION_PREFIX,    "page-watch",        watch,        True),
    (SETTINGS_ACTION_PREFIX, "settings",          settings,     True),
    (PAGE_ACT_PREFIX,        "page-action",       page_action,  True),
    (PERM_LEDGER_PREFIX,     "permission-ledger", perm_ledger,  True),
    (FORM_DRAFT_PREFIX,      "form-draft",        form_draft,   True),
    (PWA_PREFIX,             "PWA",               pwa,          True),
    (SW_REGISTER_PREFIX,     "service-worker",    sw_register,  True),
    (PUSH_SUB_PREFIX,        "push-subscription", push_sub,     True),
    (CLIP_PREFIX,            "clipboard",         clipboard,    False),
)


def dispatch(page, message: str) -> bool:
    """Match ``message`` against IPC_HANDLERS and invoke the handler.

    Returns True iff a handler matched (whether or not it succeeded;
    handler errors are logged but swallowed). Returns False if no
    prefix matched, so the caller can pass the message through to
    Qt's normal console logging.
    """
    for prefix, label, handler, parses_json in IPC_HANDLERS:
        if not message.startswith(prefix):
            continue
        payload = message[len(prefix):]
        try:
            if parses_json:
                payload = json.loads(payload)
            mw = page._get_main_window()
            if mw is not None:
                handler(page, mw, payload)
        except Exception:
            logger.exception("Failed to handle %s IPC", label)
        return True
    return False
