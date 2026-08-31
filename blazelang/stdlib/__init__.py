"""
Standard library for BlazeLang
"""

from .http import create_http_module
from .json import create_json_module
from .file import create_file_module
from .image import create_image_module

__all__ = ["create_http_module", "create_json_module", "create_file_module", "create_image_module"]
