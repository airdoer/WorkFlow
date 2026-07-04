import logging
logger = logging.getLogger("script")

# 字体颜色
RED_COLOR = "\033[31m"
YELLOW_COLOR = "\033[33m"
GREEN_COLOR = "\033[32m"
RESET_COLOR = "\033[0m"

def print_error(msg):
    logger.error(f"{msg}{RESET_COLOR}")

def print_info(msg):
    logger.info(f"{msg}{RESET_COLOR}")

def print_warn(msg):
    logger.warning(f"{msg}{RESET_COLOR}")
