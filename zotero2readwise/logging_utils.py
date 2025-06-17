import logging

def setup_logger(name="zotero2readwise", level=logging.INFO, log_file=None):
    logger = logging.getLogger(name)
    logger.propagate = False  # Prevent duplicate logs in some environments
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    logger.setLevel(level)
    return logger
