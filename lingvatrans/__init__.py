"""Lingvanex Translation API wrapper for Python."""
__all__ = ['Translator']
__version__ = '1.0.0'

from lingvatrans.client import Translator
from lingvatrans.constants import LANGUAGES, LANGCODES, LANGNAMES, ALPHA1_TO_FULL  # noqa
from lingvatrans.models import Translated, Detected  # noqa
