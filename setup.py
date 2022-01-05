#!/usr/bin/env python

"""The setup script."""

from setuptools import find_packages, setup

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
test_requirements = ['pytest>=3',]
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
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
    ],
    description="Repository for the Product Generation Executable (PGE) code utilized with the Observational Products for End-Users from Remote Sensing Analysis (OPERA) Science Data System (SDS).",
    install_requires=requirements,
    license="Apache Software License 2.0",
    long_description=readme,
    include_package_data=True,
    keywords='opera_sds_pge',
    name='opera-sds-pge',
    packages=find_packages(include=['opera', 'opera.*']),
    test_suite='test',
    tests_require=test_requirements,
    url='https://github.com/nasa/opera-sds-pge',
    version='0.1.0',
    zip_safe=False,
    extras_require={"dev": dev_requirements},
)
