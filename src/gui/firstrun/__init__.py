"""
src/gui/firstrun/__init__.py
Public API for the Luminos First Run Experience (Phase 5.9).

Usage:
    from gui.firstrun import should_show_firstrun, launch_firstrun
    if should_show_firstrun():
        launch_firstrun()
"""

from gui.firstrun.firstrun_state import is_complete


def should_show_firstrun() -> bool:
    """Return True when first_run_complete flag does not exist."""
    return not is_complete()


def launch_firstrun() -> None:
    """Launch the First Run wizard application."""
    try:
        from gui.firstrun.firstrun_app import main
        main()
    except Exception as e:
        import logging
        logging.getLogger("luminos.firstrun").warning(
            f"Failed to launch firstrun: {e}"
        )
