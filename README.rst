=============
opera-sds-pge
=============

Repository for the Product Generation Executable (PGE) code utilized with the
Observational Products for End-Users from Remote Sensing Analysis (OPERA) Science
Data System (SDS).

Prerequisites
-------------

- Python 3.8 or above

Setup for Developers
---------------------

Get the code and work on a branch:

    git clone ...
    git checkout -b "<issue number>_<issue description>"

Install a Python virtual environment, say in a `venv` directory:

    python3 -m venv venv
    source venv/bin/activate

Install the package and its dependencies for development into the virtual environment:

    pip install --editable '.[dev]'


Unit tests
----------

To launch the full set of tests, simply run the following command from within the `opera_pge` directory:

    pytest .

User Documentation
------------------

User documentation is managed with Sphinx, which is also installed in your Python virtual environment when you run `pip install --editable .[dev]`.
You can generate the documentation by hand at any time by running the following command within the `opera_pge` directory:

    sphinx-apidoc -o docs/ opera

License
-------

This library is licensed under the Apache Software License 2.0. The full text of the license can be found in this repository at LICENSE.txt.
