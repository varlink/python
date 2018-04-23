from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
import os
import sys
import unittest


here = os.path.dirname(__file__)
loader = unittest.defaultTestLoader

def suite():
    suite = unittest.TestSuite()
    for fn in os.listdir(here):
        if fn.startswith("test") and fn.endswith(".py"):
            modname = "varlink.tests." + fn[:-3]
            __import__(modname)
            module = sys.modules[modname]
            suite.addTest(loader.loadTestsFromModule(module))
    #suite.addTest(loader.loadTestsFromName('varlink.tests.testmock'))
    return suite


if __name__ == "__main__":
    unittest.main(defaultTest="suite")

