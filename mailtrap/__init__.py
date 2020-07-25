import pathlib

__version__ = '1.0.0'
ROOT_DIR = pathlib.Path(pkgutil.get_loader('mailtrap').get_filename()).parent
STATIC_DIR = ROOT_DIR / 'static'
TEMPLATES_DIR = ROOT_DIR / 'templates'
ASSETS_DIR = STATIC_DIR / 'assets'
STATIC_URL = '/static/'
