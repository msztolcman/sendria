import os
import subprocess

from setuptools import setup
from setuptools.command.build_py import build_py


class build_py_with_assets(build_py):
    def run(self):
        if not self.dry_run:
            self._build_assets()
        build_py.run(self)

    def _build_assets(self):
        asset_dir = 'mailtrap/static/assets'
        # Lame check if we have prebuilt assets. If we do so we are probably installing from a pypi package which
        # means that webassets might not be installed yet and thus we cannot build the assets now...
        if os.path.exists(asset_dir) and os.listdir(asset_dir):
            return
        args = ['webassets', '-m', 'mailtrap.web', 'build']
        with open(os.devnull, 'w') as devnull:
            subprocess.check_call(args, stderr=devnull)
            subprocess.check_call(args + ['--production'], stderr=devnull)


with open('requirements.txt') as f:
    requirements = f.read().splitlines()
with open('README.md') as f:
    readme = f.read()

setup(
    name='mailtrap',
    version='0.1.0',
    description='An SMTP server that makes all received mails accessible via a web interface and REST API.',
    long_description=readme,
    long_description_content_type='text/markdown',
    url='https://github.com/msztolcman/mailtrap',
    download_url='https://github.com/msztolcman/mailtrap',
    author='Marcin Sztolcman',
    author_email='marcin@urzenia.net',
    license='MIT',
    zip_safe=False,
    include_package_data=True,
    packages=('mailtrap', 'mailtrap_runner'),
    entry_points={
        'console_scripts': [
            'mailtrap = mailtrap_runner.__main__:main',
        ],
    },
    install_requires=requirements,
    cmdclass={'build_py': build_py_with_assets},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Environment :: No Input/Output (Daemon)',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Topic :: Communications :: Email',
        'Topic :: Software Development',
        'Topic :: System :: Networking',
        'Topic :: Utilities'
    ]
)
