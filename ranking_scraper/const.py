import os

CONFIG_FILE_ENV = 'ODC_RATINGS_CONFIG'
CONFIG_FILE_DEFAULT = 'config.json'  # in working directory
CONFIG_FILE = os.getenv(CONFIG_FILE_ENV, default=CONFIG_FILE_DEFAULT)
