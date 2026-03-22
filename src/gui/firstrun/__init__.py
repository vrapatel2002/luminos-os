"""
src/gui/firstrun/__init__.py
Public API for the Luminos First Run Setup wizard.

Usage:
    from gui.firstrun import should_show_firstrun, launch_firstrun
    if should_show_firstrun():
        launch_firstrun()
"""

from gui.firstrun.firstrun_state import is_setup_complete


def should_show_firstrun() -> bool:
    """
    Return True if the first-run setup wizard should be shown.

    Returns:
        True when the setup flag file does not exist.
    """
    return not is_setup_complete()


def launch_firstrun() -> None:
    """Launch the First Run Setup wizard application."""
    try:
        from gui.firstrun.firstrun_app import FirstRunApp
        app = FirstRunApp()
        app.run([])
    except Exception as e:
        import logging
        logging.getLogger("luminos-ai.gui.firstrun").warning(
            f"Failed to launch firstrun: {e}"
        )
