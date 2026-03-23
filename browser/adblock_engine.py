"""Enhanced ABP-style ad blocking engine with O(1) domain lookup."""

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class FilterRule:
    """A parsed ABP filter rule."""
    raw: str
    pattern: str  # The URL pattern (compiled to regex)
    regex: re.Pattern | None = None
    is_exception: bool = False
    # Options
    third_party: bool | None = None  # None = any, True = 3p only, False = 1p only
    resource_types: set = field(default_factory=set)  # empty = all types
    domains: dict = field(default_factory=dict)  # domain -> True/False (include/exclude)
    # For domain anchor rules
    anchor_domain: str = ""


class AdBlockEngine:
    """Enhanced ABP filter engine with hash-based domain lookup."""

    def __init__(self):
        self._domain_rules: dict[str, list[FilterRule]] = {}  # domain token -> rules
        self._generic_rules: list[FilterRule] = []  # rules without domain anchor
        self._exception_rules: list[FilterRule] = []
        self._dynamic_rules: dict[str, dict[str, str]] = {}  # site -> {third-party-domain -> "block"/"allow"}
        self._scriptlets: dict[str, list[tuple[str, list[str]]]] = {}  # domain -> [(scriptlet_name, args)]

    def parse_rules(self, lines: list[str]):
        """Parse a list of ABP filter rule strings."""
        for line in lines:
            line = line.strip()
            if not line or line.startswith('!') or line.startswith('['):
                continue  # comment or header

            # Cosmetic rules (handled elsewhere)
            if '##' in line or '#@#' in line:
                # But check for scriptlet rules first
                if '##+js(' in line:
                    self._parse_scriptlet(line)
                continue

            rule = self._parse_rule(line)
            if rule:
                if rule.is_exception:
                    self._exception_rules.append(rule)
                elif rule.anchor_domain:
                    token = rule.anchor_domain.split('.')[-2] if '.' in rule.anchor_domain else rule.anchor_domain
                    self._domain_rules.setdefault(token, []).append(rule)
                else:
                    self._generic_rules.append(rule)

    def _parse_rule(self, raw: str) -> FilterRule | None:
        """Parse a single ABP filter rule."""
        is_exception = raw.startswith('@@')
        if is_exception:
            raw_pattern = raw[2:]
        else:
            raw_pattern = raw

        # Split off options
        options_str = ""
        if '$' in raw_pattern:
            # Find the last $ that's not inside a regex
            idx = raw_pattern.rfind('$')
            options_str = raw_pattern[idx + 1:]
            raw_pattern = raw_pattern[:idx]

        rule = FilterRule(raw=raw, pattern=raw_pattern, is_exception=is_exception)

        # Parse options
        if options_str:
            for opt in options_str.split(','):
                opt = opt.strip()
                if opt == 'third-party':
                    rule.third_party = True
                elif opt == '~third-party':
                    rule.third_party = False
                elif opt in ('script', 'image', 'stylesheet', 'xmlhttprequest',
                             'subdocument', 'font', 'media', 'websocket',
                             'object', 'popup', 'other'):
                    rule.resource_types.add(opt)
                elif opt.startswith('domain='):
                    for d in opt[7:].split('|'):
                        if d.startswith('~'):
                            rule.domains[d[1:]] = False
                        else:
                            rule.domains[d] = True

        # Parse domain anchor
        if raw_pattern.startswith('||'):
            # Domain anchor -- extract the domain part
            domain_part = raw_pattern[2:]
            # Domain ends at ^, /, *, or end
            m = re.match(r'^([a-zA-Z0-9._-]+)', domain_part)
            if m:
                rule.anchor_domain = m.group(1)

        # Compile pattern to regex
        rule.regex = self._compile_pattern(raw_pattern)
        return rule

    def _compile_pattern(self, pattern: str) -> re.Pattern:
        """Convert an ABP URL pattern to a regex."""
        # Handle anchors
        regex = pattern
        if regex.startswith('||'):
            regex = r'^https?://([a-z0-9.-]*\.)?' + re.escape(regex[2:])
        elif regex.startswith('|'):
            regex = '^' + re.escape(regex[1:])
        else:
            regex = re.escape(regex)

        if regex.endswith('|'):
            regex = regex[:-len(re.escape('|'))] + '$'

        # Replace wildcards and separator
        regex = regex.replace(r'\*', '.*')
        regex = regex.replace(r'\^', r'[^\w\d_.%-]')

        try:
            return re.compile(regex, re.IGNORECASE)
        except re.error:
            return re.compile(re.escape(pattern), re.IGNORECASE)

    def _parse_scriptlet(self, line: str):
        """Parse a scriptlet injection rule like: domain##+js(name, arg1, arg2)"""
        parts = line.split('##+js(', 1)
        if len(parts) != 2:
            return
        domains_str = parts[0]
        scriptlet_str = parts[1].rstrip(')')

        # Parse scriptlet name and args
        args = [a.strip() for a in scriptlet_str.split(',')]
        name = args[0] if args else ""
        scriptlet_args = args[1:] if len(args) > 1 else []

        for domain in domains_str.split(','):
            domain = domain.strip()
            if domain:
                self._scriptlets.setdefault(domain, []).append((name, scriptlet_args))

    def should_block(self, url: str, source_url: str = "",
                     resource_type: str = "") -> bool:
        """Check if a URL should be blocked."""
        # Check exceptions first
        for rule in self._exception_rules:
            if self._matches(rule, url, source_url, resource_type):
                return False

        # Check domain-specific rules (O(1) lookup)
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        parts = domain.split('.')
        for i in range(len(parts)):
            token = parts[i]
            for rule in self._domain_rules.get(token, []):
                if self._matches(rule, url, source_url, resource_type):
                    return True

        # Check generic rules
        for rule in self._generic_rules:
            if self._matches(rule, url, source_url, resource_type):
                return True

        # Check dynamic rules
        if source_url:
            source_host = urlparse(source_url).hostname or ""
            target_host = domain
            site_rules = self._dynamic_rules.get(source_host, {})
            if target_host in site_rules:
                return site_rules[target_host] == "block"

        return False

    def _matches(self, rule: FilterRule, url: str, source_url: str,
                 resource_type: str) -> bool:
        """Check if a rule matches a URL."""
        # Pattern match
        if rule.regex and not rule.regex.search(url):
            return False

        # Third-party check
        if rule.third_party is not None:
            is_third_party = self._is_third_party(url, source_url)
            if rule.third_party != is_third_party:
                return False

        # Resource type check
        if rule.resource_types and resource_type:
            if resource_type not in rule.resource_types:
                return False

        # Domain option check
        if rule.domains:
            source_host = urlparse(source_url).hostname or ""
            # Check if source domain matches any domain option
            matched = None
            for d, include in rule.domains.items():
                if source_host == d or source_host.endswith('.' + d):
                    matched = include
                    break
            # If we have include domains and didn't match any, skip
            has_includes = any(v for v in rule.domains.values())
            if matched is None and has_includes:
                return False
            if matched is False:
                return False

        return True

    @staticmethod
    def _is_third_party(url: str, source_url: str) -> bool:
        """Check if url is third-party relative to source_url."""
        if not source_url:
            return False
        url_host = urlparse(url).hostname or ""
        source_host = urlparse(source_url).hostname or ""
        # Same domain or subdomain = first party
        return not (url_host == source_host or
                    url_host.endswith('.' + source_host) or
                    source_host.endswith('.' + url_host))

    # ------------------------------------------------------------------
    # Dynamic filtering
    # ------------------------------------------------------------------

    def set_dynamic_rule(self, site: str, third_party_domain: str, action: str):
        """Set a per-site dynamic rule (block/allow) for a third-party domain."""
        if site not in self._dynamic_rules:
            self._dynamic_rules[site] = {}
        self._dynamic_rules[site][third_party_domain] = action

    def remove_dynamic_rule(self, site: str, third_party_domain: str):
        """Remove a per-site dynamic rule."""
        if site in self._dynamic_rules:
            self._dynamic_rules[site].pop(third_party_domain, None)

    def get_dynamic_rules(self, site: str = "") -> dict:
        """Get dynamic rules, optionally for a specific site."""
        if site:
            return dict(self._dynamic_rules.get(site, {}))
        return dict(self._dynamic_rules)

    # ------------------------------------------------------------------
    # Scriptlet injection
    # ------------------------------------------------------------------

    def get_scriptlets_for_domain(self, domain: str) -> str:
        """Return JS code for all scriptlets that apply to a domain."""
        scripts = []
        for d, scriptlet_list in self._scriptlets.items():
            if domain == d or domain.endswith('.' + d):
                for name, args in scriptlet_list:
                    js = self._generate_scriptlet(name, args)
                    if js:
                        scripts.append(js)
        return '\n'.join(scripts)

    def _generate_scriptlet(self, name: str, args: list[str]) -> str:
        """Generate JS code for a named scriptlet."""
        SCRIPTLETS = {
            "set-constant": self._scriptlet_set_constant,
            "abort-on-property-read": self._scriptlet_abort_on_property_read,
            "abort-on-property-write": self._scriptlet_abort_on_property_write,
            "abort-current-inline-script": self._scriptlet_abort_current_inline_script,
            "remove-attr": self._scriptlet_remove_attr,
            "remove-class": self._scriptlet_remove_class,
        }
        fn = SCRIPTLETS.get(name)
        return fn(args) if fn else ""

    @staticmethod
    def _scriptlet_set_constant(args: list[str]) -> str:
        if len(args) < 2:
            return ""
        prop, value = args[0], args[1]
        val_map = {"true": "true", "false": "false", "undefined": "undefined",
                    "null": "null", "noopFunc": "function(){}", "''": "''", "0": "0"}
        js_val = val_map.get(value, f"'{value}'")
        parts = prop.split('.')
        if len(parts) == 1:
            return f"Object.defineProperty(window, '{prop}', {{value: {js_val}, writable: false, configurable: false}});"
        obj = '.'.join(parts[:-1])
        key = parts[-1]
        return f"try {{ Object.defineProperty({obj}, '{key}', {{value: {js_val}, writable: false, configurable: false}}); }} catch(e) {{}}"

    @staticmethod
    def _scriptlet_abort_on_property_read(args: list[str]) -> str:
        if not args:
            return ""
        prop = args[0]
        return f"Object.defineProperty(window, '{prop}', {{get: function() {{ throw new ReferenceError('{prop}'); }}}});"

    @staticmethod
    def _scriptlet_abort_on_property_write(args: list[str]) -> str:
        if not args:
            return ""
        prop = args[0]
        return f"Object.defineProperty(window, '{prop}', {{set: function() {{ throw new ReferenceError('{prop}'); }}}});"

    @staticmethod
    def _scriptlet_abort_current_inline_script(args: list[str]) -> str:
        if not args:
            return ""
        prop = args[0]
        search = args[1] if len(args) > 1 else ""
        if search:
            return (
                "(function() {\n"
                f"    var o = Object.getOwnPropertyDescriptor(window, '{prop}') || {{}};\n"
                f"    var orig = o.get || function() {{ return window._{prop}; }};\n"
                f"    Object.defineProperty(window, '{prop}', {{\n"
                "        get: function() {\n"
                "            var s = document.currentScript;\n"
                f"            if (s && s.textContent.indexOf('{search}') !== -1) throw new ReferenceError('{prop}');\n"
                "            return orig.call(this);\n"
                "        },\n"
                f"        set: function(v) {{ window._{prop} = v; }}\n"
                "    });\n"
                "})();"
            )
        return f"Object.defineProperty(window, '{prop}', {{get: function() {{ throw new ReferenceError('{prop}'); }}}});"

    @staticmethod
    def _scriptlet_remove_attr(args: list[str]) -> str:
        if not args:
            return ""
        attr = args[0]
        selector = args[1] if len(args) > 1 else f"[{attr}]"
        return f"document.querySelectorAll('{selector}').forEach(function(el) {{ el.removeAttribute('{attr}'); }});"

    @staticmethod
    def _scriptlet_remove_class(args: list[str]) -> str:
        if not args:
            return ""
        cls = args[0]
        selector = args[1] if len(args) > 1 else f".{cls}"
        return f"document.querySelectorAll('{selector}').forEach(function(el) {{ el.classList.remove('{cls}'); }});"

    @property
    def rule_count(self) -> int:
        total = len(self._generic_rules) + len(self._exception_rules)
        for rules in self._domain_rules.values():
            total += len(rules)
        return total
