#!/usr/bin/env python

"""The setup script."""

from setuptools import find_packages, setup

import opera

with open('README.rst') as readme_file:
    readme = readme_file.read()

requirements = [
    "jsonschema",
    "flake8",
    "flake8-docstrings",
    "flake8-import-order",
    "PyYAML",
    "pylint",
    "pytest",
    "pytest-cov",
    "yamale"
]
test_requirements = ['pytest>=3', ]
dev_requirements = [
    "coverage>=4.5.4",
    "sphinx>=1.8.5",
    "sphinx-argparse",
    "sphinx-rtd-theme>=1.0.0",
    "sphinxcontrib-napoleon",
    "sphinxcontrib-websupport",
    "pytest>=6.2.4",
]

setup(
    author="California Institute of Technology",
    author_email='scott.collins@jpl.nasa.gov',
    python_requires='>=3.10',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
    ],
    description=opera.__summary__,
    install_requires=requirements,
    license="Apache Software License 2.0",
    long_description=readme,
    include_package_data=True,
    keywords=['opera', 'jpl', 'pge', 'sas', 'sds'],
    name=opera.__title__,
    packages=find_packages(include=['opera', 'opera.*']),
    test_suite='test',
    tests_require=test_requirements,
    url=opera.__uri__,
    version=opera.__version__,
    zip_safe=False,
    extras_require={"dev": dev_requirements},
)
