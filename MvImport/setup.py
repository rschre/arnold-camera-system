from pathlib import Path
from setuptools import setup, find_packages

here = Path(__file__).parent
readme = (here / "README.md").read_text(encoding="utf-8") if (here / "README.md").exists() else ""

setup(
    name="mvimport",
    version="0.1.0",
    description="Utilities for importing and accessing Hikrobot MVS SDK camera data (MvImport package)",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Hikrobot",
    author_email="global.support@hikrobotics.com",
    url="https://www.hikrobotics.com/en/machinevision/service/download/",
    # only package the contents of this folder (and its subpackages)
    packages=find_packages(where=".", exclude=("tests", "docs")),
    package_dir={"": "."},
    include_package_data=True,
    install_requires=[
        # e.g. "numpy>=1.20"
    ],
    python_requires=">=3.8",
)