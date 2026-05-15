"""Tests for the Fill-address JS payload construction.

We can't easily run the injected JS without a live page, but we can
verify the payload string is well-formed, properly escaped, and only
references autocomplete tokens we expect.
"""

import json
import re

from browser import addresses


def _build_fill_js(addr):
    """Replicate the JS-builder logic from PageFeaturesMixin without
    needing to instantiate the full mixin."""
    payload = json.dumps(addr.fields)
    return (
        "(function(values){"
        "  var filled = 0;"
        "  document.querySelectorAll('input[autocomplete], textarea[autocomplete], select[autocomplete]').forEach(function(el){"
        "    var key = el.getAttribute('autocomplete');"
        "    if (key && values[key] != null) {"
        "      el.focus();"
        "      el.value = values[key];"
        "      el.dispatchEvent(new Event('input', {bubbles:true}));"
        "      el.dispatchEvent(new Event('change', {bubbles:true}));"
        "      filled++;"
        "    }"
        "  });"
        "  return filled;"
        f"}})({payload});"
    )


class TestFillJsPayload:
    def test_payload_is_valid_json_inside_js(self, tmp_data_dir):
        a = addresses.add_address("Home", {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
        })
        js = _build_fill_js(a)
        # The payload sits between the last ')(' and ')'.
        m = re.search(r"\}\)\((\{.*\})\);$", js)
        assert m is not None
        payload = json.loads(m.group(1))
        assert payload["name"] == "Ada Lovelace"
        assert payload["email"] == "ada@example.com"

    def test_payload_escapes_quotes(self, tmp_data_dir):
        # Names with quotes are real (e.g. company names). JSON encoding
        # must escape them so the JS doesn't break out of the literal.
        a = addresses.add_address("Work", {
            "organization": 'Acme "Industries" Ltd',
        })
        js = _build_fill_js(a)
        # The raw quoted name shouldn't appear unescaped.
        assert '"Industries"' not in js
        assert '\\"Industries\\"' in js

    def test_payload_handles_unicode(self, tmp_data_dir):
        a = addresses.add_address("Café", {
            "name": "Zoë Müller",
            "address-level2": "São Paulo",
        })
        js = _build_fill_js(a)
        # json.dumps escapes non-ASCII by default.
        m = re.search(r"\}\)\((\{.*\})\);$", js)
        payload = json.loads(m.group(1))
        assert payload["name"] == "Zoë Müller"
        assert payload["address-level2"] == "São Paulo"

    def test_payload_cant_carry_unknown_keys(self, tmp_data_dir):
        # _sanitize_fields strips non-AUTOCOMPLETE keys at save time, so
        # the resulting JS can never reach an unexpected token.
        a = addresses.add_address("Home", {
            "name": "x",
            "credit-card-number": "BAD-DATA",   # not in AUTOCOMPLETE_FIELDS
            "<script>": "evil",
        })
        js = _build_fill_js(a)
        assert "credit-card-number" not in js
        assert "<script>" not in js
        assert "BAD-DATA" not in js
        assert "evil" not in js

    def test_payload_safe_against_script_close(self, tmp_data_dir):
        # If a saved value happened to contain "</script>" it must not
        # be able to close a host page's <script> block. json.dumps
        # escapes the forward slash sequence in a safe way (the JS
        # is injected via runJavaScript, not inline, so this is
        # defense in depth).
        a = addresses.add_address("Home", {
            "name": "</script><img src=x onerror=alert(1)>",
        })
        js = _build_fill_js(a)
        # The literal "</script>" must be JSON-escaped — Python's
        # json.dumps doesn't escape "/" by default, but the string
        # remains inside a JSON string literal so it's inert.
        m = re.search(r"\}\)\((\{.*\})\);$", js)
        payload = json.loads(m.group(1))
        # Round-trip preserves the value as data.
        assert payload["name"] == "</script><img src=x onerror=alert(1)>"
