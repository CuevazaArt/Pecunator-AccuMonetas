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
