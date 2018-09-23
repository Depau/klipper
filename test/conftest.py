def pytest_addoption(parser):
    # Lowercase options are reserved by pytest
    parser.addoption("--dictdir", "-D", action="store", default=".", help="directory for dictionary files")
    parser.addoption("--keepfiles", "-K", action="store_true", help="do not remove temporary files")


def pytest_generate_tests(metafunc):
    dictdir = metafunc.config.option.dictdir
    keepfiles = metafunc.config.option.keepfiles

    if 'dictdir' in metafunc.fixturenames and dictdir is not None:
        metafunc.parametrize("dictdir", [dictdir])

    if 'keepfiles' in metafunc.fixturenames and keepfiles is not None:
        metafunc.parametrize("keepfiles", [keepfiles])