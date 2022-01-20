.. highlight:: shell

============
Contributing
============

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

You can contribute in many ways:

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs at https://github.com/nasa/opera-sds-pge/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "bug" and "help
wanted" is open to whoever wants to implement it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues for features. Anything tagged with "good first issue",
"enhancement" and "help wanted" is open to whoever wants to implement it. However,
issues tagged with "must have" are typically mission-critical features and should be
left to developers within the NASA organization.

Write Documentation
~~~~~~~~~~~~~~~~~~~

opera-sds-pge could always use more documentation, whether as part of the
official opera-sds-pge docs, in docstrings, or even on the web in blog posts,
articles, and such.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue at https://github.com/nasa/opera-sds-pge/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.

Get Started!
------------

Ready to contribute? Here's how to set up `opera_sds_pge` for local development.

1. Fork the `opera_sds_pge` repo on GitHub.
2. Clone your fork locally::

    $ git clone git@github.com:your_name_here/opera_sds_pge.git

3. Install your local copy into a virtualenv::

    $ python3 -m venv venv
    $ source venv/bin/activate
    $ cd opera_pge/
    $ pip install --editable '.[dev]'

4. Create a branch for local development::

    $ git checkout -b "<issue number>_<issue description>"

   Now you can make your changes locally.

5. When you're done making changes, check that your changes pass flake8 and the
   unit tests::

    $ flake8 --config opera_pge/.flake8 --application-import-names opera_pge/src
    $ pytest opera_pge/src

6. Commit your changes and push your branch to GitHub::

    $ git add .
    $ git commit -m "Your detailed description of your changes."
    $ git push origin name-of-your-bugfix-or-feature

7. Submit a pull request through the GitHub website.

Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests that exercise add functionality, and/or
   fix existing tests broken by any changes.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring (numpy style please),
   and add the feature to the list in README.rst.
3. The pull request should work for Python 3.8 and above.
