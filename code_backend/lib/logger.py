import logging
from logging.handlers import RotatingFileHandler
import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

LOG_FORMAT = '[%(asctime)s] [%(name)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# RotatingFileHandler
handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=1000 * 1024 * 1024,
    backupCount=5,
    encoding='utf-8'
)
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
root_logger.addHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
root_logger.addHandler(console_handler)


def log_info(module: str, msg: str, *args, **kwargs):
    logger = logging.getLogger(module)
    logger.info(msg, *args, stacklevel=2, **kwargs)


def log_error(module: str, msg: str, *args, **kwargs):
    logger = logging.getLogger(module)
    logger.error(msg, *args, stacklevel=2, **kwargs)


def log_debug(module: str, msg: str, *args, **kwargs):
    logger = logging.getLogger(module)
    logger.debug(msg, *args, stacklevel=2, **kwargs)
