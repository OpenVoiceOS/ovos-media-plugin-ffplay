# START_VERSION_BLOCK
VERSION_MAJOR = 0
VERSION_MINOR = 0
VERSION_BUILD = 3
VERSION_ALPHA = 4
# END_VERSION_BLOCK

# derived from the VERSION_BLOCK above so pyproject can read it as the
# single packaging source of truth (dynamic = ["version"]).
__version__ = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_BUILD}" + (
    f"a{VERSION_ALPHA}" if VERSION_ALPHA else "")
