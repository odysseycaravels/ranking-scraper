from ranking_scraper.db import get_session


class Scraper(object):
    """ Abstract scraper class """
    def __init__(self, session):
        self.session = session or get_session()

    def pull_event_data(self, game_code, from_dt, to_dt, countries=None):
        """
        Find events and create corresponding Event instances by the given criteria.

        Note that this should only create the Event instances and not populate the corresponding set data. The latter
        can take a significant amount of time and thus should be handled by a different job / request.

        :type game_code: str
        :type from_dt: datetime.datetime
        :type to_dt: datetime.datetime
        :type countries: typing.List or None
        """
        raise NotImplementedError()
