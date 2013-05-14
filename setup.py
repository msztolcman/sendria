# coding=utf-8

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
        args = ['webassets', '-m', 'maildump.web', 'build']
        with open(os.devnull, 'w') as devnull:
            subprocess.check_call(args, stderr=devnull)
            subprocess.check_call(args + ['--production'], stderr=devnull)


with open('requirements.txt') as f:
    requirements = f.read().splitlines()
with open('README.md') as f:
    readme = f.read()


setup(
    name='maildump',
    version='0.1',
    description='A SMTP server that makes all received mails via a web interface and REST API.',
    long_description=readme,
    url='https://github.com/ThiefMaster/maildump',
    download_url='https://github.com/ThiefMaster/maildump',
    author=u'Adrian Mönnich',
    author_email='adrian@planetcoding.net',
    license='MIT',
    zip_safe=False,
    include_package_data=True,
    packages=('maildump', 'maildump_runner'),
    entry_points={
        'console_scripts': [
            'maildump = maildump_runner.__main__:main',
        ],
    },
    install_requires=requirements,
    cmdclass={'build_py': build_py_with_assets},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
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