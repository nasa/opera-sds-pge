#!/usr/bin/env python

"""The setup script."""

from setuptools import find_packages, setup

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = ["jsonschema", "PyYAML", "pytest-cov", "yamale"]
test_requirements = [
    "pytest>=3",
]
dev_requirements = [
    "bump2version>=0.5.11",
    "wheel>=0.33.6",
    "watchdog>=0.9.0",
    "flake8>=3.7.8",
    "tox>=3.14.0",
    "coverage>=4.5.4",
    "Sphinx>=1.8.5",
    "twine>=1.14.0",
    "pytest>=6.2.4",
    "sphinx-rtd-theme>=1.0.0",
    "pre-commit>=2.16.0",
]

setup(
    author="Drew Meyers",
    author_email="drewm@mit.edu",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description=(
        "Repository for the Product Generation Executable (PGE) code utilized with the Observational Products for"
        " End-Users from Remote Sensing Analysis (OPERA) Science Data System (SDS)."
    ),
    install_requires=requirements,
    license="Apache Software License 2.0",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="opera_sds_pge",
    name="opera-sds-pge",
    packages=find_packages(include=["opera", "opera.*"]),
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/drewmee/opera-sds-pge",
    version="0.1.0",
    zip_safe=False,
    extras_require={"dev": dev_requirements},
)
