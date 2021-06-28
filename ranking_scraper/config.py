import json

from ranking_scraper import const

_config = None


def get_config(fpath=None):
    global _config
    if _config:
        return _config
    fpath = fpath or const.CONFIG_FILE  # arg > env > default
    with open(fpath, 'rt') as rf:
        _config = json.load(rf)
    return _config
