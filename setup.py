from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()


def get_version():
    """Read the version from the VERSION file."""
    with open(here / "VERSION") as vf:
        return vf.readline().strip().lower()


setup(
    name="smartmeter",
    version="2.0.0",  # Required
    description="Read data from the digital electricity meter.",
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
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="digital meter, energy, electricity, power control",
    packages=find_packages(where="app"),
    python_requires=">=3.6, <4",
    # install_requires=["peppercorn"],  # Optional
    # extras_require={  # Optional
    #    "dev": ["check-manifest"],
    #    "test": ["coverage"],
    # },
    # package_data={  # Optional
    #    "sample": ["package_data.dat"],
    # },
    # data_files=[("my_data", ["data/data_file"])],  # Optional
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # `pip` to create the appropriate form of executable for the target
    # platform.
    #
    # For example, the following would provide a command called `sample` which
    # executes the function `main` from this package when invoked:
    # entry_points={  # Optional
    #    "console_scripts": [
    #        "sample=sample:main",
    #    ],
    # },
    project_urls={
        # "Documentation:": "blah"
        "Bug Reports": "https://gitlab.com/wimdh/smartmeter/-/issues",
        "Source": "https://gitlab.com/wimdh/smartmeter/",
    },
)
