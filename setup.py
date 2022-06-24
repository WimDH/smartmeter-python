from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()


def get_version():
    """Read the version from the VERSION file."""
    with open(here / "VERSION") as vf:
        return vf.readline().strip().lower()


setup(
    name="smartmeter",
    version=get_version(),
    description="Read data from the (belgian) digital electricity meter.",
    url="https://gitlab.com/wimdh/smartmeter",
    author="Wim De Hul",
    author_email="smartmeter@dehul.net",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Other Audience",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="digital meter, energy, electricity, power control",
    packages=find_packages(where="smartmeter"),
    python_requires=">=3.6, <3.9",
    data_files=[("config.sample.ini", ["config.sample.ini"])],
    entry_points={
        "console_scripts": [
            "smartmeter=smartmeter.main:main",
        ],
    },
    project_urls={
        # "Documentation:": "blah"
        "Bug Reports": "https://gitlab.com/wimdh/smartmeter/-/issues",
        "Source": "https://gitlab.com/wimdh/smartmeter/",
    },
)
