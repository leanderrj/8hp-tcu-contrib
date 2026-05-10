"""End-to-end scenario tests.

Each test in this directory walks the Plant model + LIN pump simulator
through a realistic drive episode (cold start, P→D shift, gear cycle,
forward-to-reverse, brown-out, etc.) and asserts the resulting state /
CAN traces / fault flags are what the HARA's safety requirements demand.

Layout follows CarOS's `tests/scenarios/test_drive_cycle.py` pattern.
"""
