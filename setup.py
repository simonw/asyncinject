from setuptools import setup
import os

VERSION = "0.2"


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="asyncinject",
    description="Run async workflows using pytest-fixtures-style dependency injection",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Simon Willison",
    url="https://github.com/simonw/asyncinject",
    project_urls={
        "Issues": "https://github.com/simonw/asyncinject/issues",
        "CI": "https://github.com/simonw/asyncinject/actions",
        "Changelog": "https://github.com/simonw/asyncinject/releases",
    },
    license="Apache License, Version 2.0",
    version=VERSION,
    packages=["asyncinject"],
    install_requires=[],
    extras_require={"test": ["pytest", "pytest-asyncio"]},
    python_requires=">=3.6",
)
