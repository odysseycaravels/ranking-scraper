from ranking_scraper.db import get_session


class Scraper(object):
    """ Abstract scraper class """
    def __init__(self, session):
        self.session = session or get_session()

    def pull_tournaments(self, game_code, from_dt, to_dt, countries=None,
                         skip_retrieving_sets=False):
        raise NotImplementedError()
