import os
import logging
import sys
import time
import json
import re
import pprint

class MatterRuleEngine(object):
    _args = None

    def __init__(self,args):    
        self._args = args

    def jsonDumps(self, dm):
        #this method is required as dumps doesnt work with advanced types
        dmstr = pprint.pformat(dm)
        dmstr = dmstr.replace(" ", "")
        dmstr = dmstr.replace("\n", "")
        dmstr = dmstr.replace("<class'", "\"")
        dmstr = dmstr.replace("\'>", "\"")
        dmstr = dmstr.replace("False", "false")
        dmstr = dmstr.replace("True", "true")
        dmstr = dmstr.replace("Null", "null")
        line = re.sub(r"(\d+)(:)", "\"\g<1>\":", dmstr)
        return line

    def testDumps(self, dm):
        #this method is required as dumps doesnt work with advanced types
        dmstr = pprint.pformat(dm)
        return dmstr



