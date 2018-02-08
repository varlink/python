from distutils.core import setup

setup(
    name = "varlink",
    packages = ["varlink"],
    version = "3",
    description = "Varlink",
    author = "Lars Karlitski<lars@karlitski.net>, Harald Hoyer<harald@redhat.com>",
    author_email = "harald@redhat.com",
    url = "https://github.com/varlink/python-varlink",
    license = "ASL 2.0",
    keywords = "ipc varlink rpc",
    python_requires='>=3.5',
    package_data = {
        "varlink": [ "*.varlink" ]
    }
)
