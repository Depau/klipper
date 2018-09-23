# Regression test helper script
#
# Copyright (C) 2018  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
import os
import subprocess
import sys

import pytest

TEMP_GCODE_FILE = "_test_.gcode"
TEMP_LOG_FILE = "_test_.log"
TEMP_OUTPUT_FILE = "_test_output"


######################################################################
# Test cases
######################################################################

class error(Exception):
    pass

class TestCase:
    __test__ = False

    def __init__(self, fname, dictdir, tempdir, verbose, keepfiles):
        self.fname = fname
        self.dictdir = os.path.abspath(dictdir)
        self.tempdir = os.path.abspath(tempdir)
        self.verbose = verbose
        self.keepfiles = keepfiles

    def relpath(self, fname, rel='test'):
        if rel == 'dict':
            reldir = self.dictdir
        elif rel == 'temp':
            reldir = self.tempdir
        else:
            reldir = os.path.dirname(self.fname)
        return os.path.join(reldir, fname)
    def parse_test(self):
        # Parse file into test cases
        config_fname = gcode_fname = dict_fnames = None
        should_fail = multi_tests = False
        gcode = []
        f = open(self.fname, 'r')
        for line in f:
            cpos = line.find('#')
            if cpos >= 0:
                line = line[:cpos]
            parts = line.strip().split()
            if not parts:
                continue
            if parts[0] == "CONFIG":
                if config_fname is not None:
                    # Multiple tests in same file
                    if not multi_tests:
                        multi_tests = True
                        self.launch_test(config_fname, dict_fnames,
                                         gcode_fname, gcode, should_fail)
                config_fname = self.relpath(parts[1])
                if multi_tests:
                    self.launch_test(config_fname, dict_fnames,
                                     gcode_fname, gcode, should_fail)
            elif parts[0] == "DICTIONARY":
                dict_fnames = [self.relpath(parts[1], 'dict')]
                for mcu_dict in parts[2:]:
                    mcu, fname = mcu_dict.split('=', 1)
                    dict_fnames.append('%s=%s' % (
                        mcu.strip(), self.relpath(fname.strip(), 'dict')))
            elif parts[0] == "GCODE":
                gcode_fname = self.relpath(parts[1])
            elif parts[0] == "SHOULD_FAIL":
                should_fail = True
            else:
                gcode.append(line.strip())
        f.close()
        if not multi_tests:
            self.launch_test(config_fname, dict_fnames,
                             gcode_fname, gcode, should_fail)
    def launch_test(self, config_fname, dict_fnames, gcode_fname, gcode,
                    should_fail):
        gcode_is_temp = False
        if gcode_fname is None:
            gcode_fname = self.relpath(TEMP_GCODE_FILE, 'temp')
            gcode_is_temp = True
            f = open(gcode_fname, 'w')
            f.write('\n'.join(gcode))
            f.close()
        elif gcode:
            raise error("Can't specify both a gcode file and gcode commands")
        if config_fname is None:
            raise error("config file not specified")
        if dict_fnames is None:
            raise error("data dictionary file not specified")
        # Call klippy
        sys.stderr.write("    Starting %s (%s)\n" % (
            self.fname, os.path.basename(config_fname)))
        args = [sys.executable, '-m', 'klippy', config_fname,
                '-i', gcode_fname, '-o', self.relpath(TEMP_OUTPUT_FILE, "temp"), '-v']
        for df in dict_fnames:
            args += ['-d', df]
        if not self.verbose:
            args += ['-l', self.relpath(TEMP_LOG_FILE, "temp")]
        res = subprocess.call(args, cwd=os.path.dirname(__file__))
        is_fail = (should_fail and not res) or (not should_fail and res)
        if is_fail:
            if not self.verbose:
                self.show_log()
            if should_fail:
                raise error("Test failed to raise an error")
            raise error("Error during test")
        # Do cleanup
        if self.keepfiles:
            return
        for fname in os.listdir(self.tempdir):
            if fname.startswith(TEMP_OUTPUT_FILE):
                os.unlink(fname)
        if not self.verbose:
            os.unlink(self.relpath(TEMP_LOG_FILE, "temp"))
        else:
            sys.stderr.write('\n')
        if gcode_is_temp:
            os.unlink(gcode_fname)
    def run(self):
        self.parse_test()
    def show_log(self):
        f = open(self.relpath(TEMP_LOG_FILE, "temp"), 'rb')
        data = f.read()
        f.close()
        sys.stdout.write(data)


class TestFile:
    @pytest.mark.parametrize(
        'file', map(
            lambda f: os.path.join(os.path.dirname(__file__), f),
            filter(
                lambda f: f.endswith(".test"),
                os.listdir(os.path.dirname(__file__))
            )
        )
    )
    def test_file(self, file, dictdir, tmpdir, keepfiles):
        tc = TestCase(file, str(dictdir), str(tmpdir), pytest.config.getoption("verbose") > 0, keepfiles)
        tc.run()
