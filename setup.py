from setuptools import setup

def local_scheme(_):
    """Enables a version format so that upload to TestPyPI is successful.
     For example: 2.6.2.dev8
     See https://github.com/pypa/setuptools_scm/issues/342.
     """
    return ""

setup(
    use_scm_version={"local_scheme": "no-local-version"},
    setup_requires=['setuptools_scm'],
)
