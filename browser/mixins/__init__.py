"""Mixin modules for MainWindow."""

from .tabs import TabMixin
from .navigation import NavigationMixin
from .content_blocking import ContentBlockingMixin
from .password_manager import PasswordMixin
from .page_features import PageFeaturesMixin
from .settings import SettingsMixin
from .browser_actions import BrowserActionsMixin
from .data_management import DataManagementMixin
from .session import SessionMixin

__all__ = [
    "TabMixin",
    "NavigationMixin",
    "ContentBlockingMixin",
    "PasswordMixin",
    "PageFeaturesMixin",
    "SettingsMixin",
    "BrowserActionsMixin",
    "DataManagementMixin",
    "SessionMixin",
]
