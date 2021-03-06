# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the PyMVPA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Test some base functionality which did not make it into a separate unittests"""

import os
import unittest

from mvpa.testing.tools import *
from mvpa.base.info import wtf

@with_tempfile()
def test_wtf(filename):
    """Very basic testing -- just to see if it doesn't crash"""

    sinfo = str(wtf())
    sinfo_excludes = str(wtf(exclude=['process']))
    ok_(len(sinfo) > len(sinfo_excludes))
    ok_(not 'Process Info' in sinfo_excludes)

    # check if we could store and load it back
    wtf(filename)
    try:
        sinfo_from_file = '\n'.join(open(filename, 'r').readlines())
    except Exception, e:
        raise AssertionError(
            'Testing of loading from a stored a file has failed: %r'
            % (e,))
