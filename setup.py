from setuptools import setup, find_packages

setup(
    name="dataforge",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi==0.103.1",
        "uvicorn==0.23.2",
        "pydantic==2.3.0",
        "python-multipart==0.0.6",
        "jinja2==3.1.2",
        "pandas==2.1.0",
        "openpyxl==3.1.2",
        "lxml==4.9.3",
        "pyyaml==6.0.1",
    ],
)