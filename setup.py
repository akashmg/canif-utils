from setuptools import find_packages, setup

setup(
    name="canifutils",
    version="0.1.0",
    description="Utilities for interfacing with CAN",
    author="Akash Gujarati",
    author_email="akashmgujarati@gmail.com",
    packages=find_packages(),
    include_package_data=True,
    install_requires=["python-can", "cantools"],
    python_requires=">=3.7",
)
