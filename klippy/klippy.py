#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import os
import sys

if __name__ == "__main__":
    # This will work in Python 2 as long as all imports are relative, i.e.
    # from . import reactor       # Py2+Py3
    # from klippy import reactor  # Py3 only
    sys.path.pop(0)
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from klippy import main
    main()