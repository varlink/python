from distutils.core import setup

setup(
    name = "varlink",
    packages = ["varlink"],
    version = "1",
    description = "Varlink",
    author = "Lars Karlitski",
    author_email = "lars@karlitski.net",
    url = "https://github.com/varlink/python-varlink",
    license = "ASL2.0",
    package_data = {
        "varlink": [ "*.varlink" ]
    }
)
