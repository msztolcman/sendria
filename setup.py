# coding=utf-8

from distutils.core import setup

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
    install_requires=requirements
)