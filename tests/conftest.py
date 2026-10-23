"""Shared test setup.

Decision motion (the 170 ms stamp and the progress tween) defers the queue
advance to a Tk timer. Most tests drive the UI synchronously and check the
next record straight after a decision, so they run with reduced motion,
exactly as a user with Windows animations turned off would. Tests that cover
motion switch it on explicitly with ``display_prefs.set_reduced_motion``.

The light palette is pinned (``SW_THEME``) so a dark Windows setting on the
test machine cannot change what the suite renders, and app settings go to a
throwaway file (``SW_SETTINGS_PATH``) instead of the user's real profile.
"""
import os
import tempfile

os.environ.setdefault("SW_REDUCE_MOTION", "1")
os.environ.setdefault("SW_THEME", "light")
os.environ.setdefault(
    "SW_SETTINGS_PATH", os.path.join(tempfile.mkdtemp(prefix="swb-test-settings-"), "settings.json"),
)
