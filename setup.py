import os
import sys

from setuptools import setup
from setuptools import find_packages

version = "0.0.2"

install_requires = [
    "acme>=0.29.0",
    "certbot>=0.31.0",
    'setuptools>=41.6.0',
    "requests",
    "mock",
    "requests-mock",
]

if not os.environ.get('SNAP_BUILD'):
    install_requires.extend([
        # We specify the minimum acme and certbot version as the current plugin
        # version for simplicity. See
        # https://github.com/certbot/certbot/issues/8761 for more info.
        'acme>=0.29.0',
        'certbot>=0.31.0',
    ])
elif 'bdist_wheel' in sys.argv[1:]:
    raise RuntimeError('Unset SNAP_BUILD when building wheels '
                       'to include certbot dependencies.')
if os.environ.get('SNAP_BUILD'):
    install_requires.append('packaging')

docs_extras = [
    'Sphinx>=1.0',  # autodoc_member_order = 'bysource', autodoc_default_flags
    'sphinx_rtd_theme',
]

setup(
    name="certbot-dns-vashosting",
    version=version,
    description="vashosting vps centrum api DNS Authenticator plugin for Certbot",
    url="https://github.com/m42e/certbot-dns-ispconfig",
    author="Jakub Vrchota",
    author_email="jamesvradio@gmail.com",
    license="Apache License 2.0",
    python_requires=">=2.7.16",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Plugins",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Security",
        "Topic :: System :: Installation/Setup",
        "Topic :: System :: Networking",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
    ],
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    entry_points={
        "certbot.plugins": [
            "dns-vh = certbot_dns_vashosting.dns_vashosting:Authenticator"
        ]
    },
)
