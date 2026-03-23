"""Permission Ledger — audit log for site permission usage."""

import csv
import time
from .db import get_db


def log_usage(host: str, feature: str, action: str):
    """Record a permission usage event."""
    get_db().log_permission_usage(host, feature, action)


def get_usage(host: str | None = None, limit: int = 500) -> list[dict]:
    """Get recent permission usage events."""
    return get_db().get_permission_usage(host, limit)


def get_anomalies(threshold: int = 10, hours: int = 1) -> list[dict]:
    """Detect sites using permissions more than *threshold* times per *hours*."""
    return get_db().get_permission_anomalies(threshold, hours)


def export_log(path: str, host: str | None = None):
    """Export permission usage log to CSV."""
    get_db().export_permission_log(path, host)
