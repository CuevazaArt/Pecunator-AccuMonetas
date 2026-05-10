import logging

def pytest_configure():
    """Disable disk logging during tests to prevent poisoning alerts.log and other production logs."""
    # Temporarily set the root logger and pecunator loggers to WARNING to reduce noise,
    # and remove FileHandlers so we don't write to the real data_dir.
    logger = logging.getLogger("pecunator")
    logger.setLevel(logging.WARNING)
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)

import pytest

@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all module-level singletons before/after each test."""
    def _clear():
        import runtime.core.api_fuse as api_fuse
        api_fuse._fuse = None
        import runtime.core.hub_state as hub_state
        hub_state._instance = None
        import runtime.core.alert_dispatcher as alert_dispatcher
        alert_dispatcher._dispatcher = None
        import runtime.core.bot_coordinator as bot_coordinator
        bot_coordinator._coordinator = None
        import runtime.core.weight_governor as weight_governor
        weight_governor._governor = None
        import runtime.core.symmetry_guard as symmetry_guard
        symmetry_guard._guard = None
        import runtime.core.telemetry_collector as tc
        tc._collector = None
    _clear()
    yield
    _clear()
