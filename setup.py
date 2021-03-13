import os
import subprocess
import shutil

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py

requirements = [
    'aiohttp',
    'aiohttp-basicauth',
    'aiohttp-jinja2',
    'aiosmtpd>=1.4.2',
    'aiosqlite',
    'beautifulsoup4',
    'cssmin',
    'html5lib',
    'lockfile',
    'passlib',
    'python-daemon',
    'pytz',
    'pyscss',
    'structlog',
    'webassets',
]


class BuildPyWithAssets(build_py):
    def run(self):
        if not self.dry_run:
            self._build_assets()
        build_py.run(self)

    def _build_assets(self):
        asset_dir = 'sendria/static/assets'
        # Lame check if we have prebuilt assets. If we do so we are probably installing from a pypi package which
        # means that webassets might not be installed yet and thus we cannot build the assets now...
        if os.path.exists(asset_dir) and os.listdir(asset_dir):
            return

        webassets = shutil.which('webassets')
        if not webassets:
            print("Cannot find webassets. Please execute manually: /path/to/webassets -m sendria.build_assets build'")
            return

        args = ['webassets', '-m', 'sendria.build_assets', 'build']
        with open(os.devnull, 'w') as devnull:
            subprocess.check_call(args, stderr=devnull)
            subprocess.check_call(args + ['--production'], stderr=devnull)


with open('README.md') as f:
    readme = f.read()

setup(
    name='sendria',
    version='2.1.0',
    description='An SMTP server that makes all received mails accessible via a web interface and REST API.',
    long_description=readme,
    long_description_content_type='text/markdown',
    url='https://github.com/msztolcman/sendria',
    project_urls={
        'GitHub: issues': 'https://github.com/msztolcman/sendria/issues',
        'GitHub: repo': 'https://github.com/msztolcman/sendria',
    },
    download_url='https://github.com/msztolcman/sendria',
    author='Marcin Sztolcman',
    author_email='marcin@urzenia.net',
    license='MIT',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(),
    python_requires='>=3.7',
    entry_points={
        'console_scripts': [
            'sendria = sendria.cli:main',
        ],
    },
    install_requires=requirements,
    cmdclass={'build_py': BuildPyWithAssets},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Environment :: No Input/Output (Daemon)',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Operating System :: MacOS :: MacOS X',
        'Topic :: Communications :: Email',
        'Topic :: Software Development',
        'Topic :: System :: Networking',
        'Topic :: Utilities',
        'Framework :: AsyncIO',
    ]
)
