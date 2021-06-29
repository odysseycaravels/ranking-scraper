import logging
import time

logging.Formatter.converter = time.gmtime  # Use UTC time


def configure_logging(logger_name='ranking_scraper', log_level=logging.WARNING):
    logger = logging.getLogger(logger_name)
    cout = logging.StreamHandler()
    if log_level == logging.DEBUG:
        fmt = '%(asctime)s - [%(levelname)-7s] %(module)s:%(funcName)s - %(message)s'
    else:
        fmt = '%(asctime)s - [%(levelname)s] %(message)s'
    formatter = logging.Formatter(fmt=fmt, datefmt='%y%m%dZ%H%M%S')
    cout.setFormatter(formatter)
    logger.setLevel(log_level)
    cout.setLevel(log_level)
    logger.addHandler(cout)
