# module required for webassets
from .http.core import configure_assets

environment = configure_assets(False, False)
