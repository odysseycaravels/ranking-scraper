import copy
import itertools
import json
import logging
import time
from urllib.error import HTTPError
from pprint import pprint as pp
from graphqlclient import GraphQLClient

from ranking_scraper.model import Game, Event
from ranking_scraper.smashgg import queries
from ranking_scraper.config import get_config
from ranking_scraper.scraper import Scraper

_l = logging.getLogger(__name__)

SMASHGG_API_ENDPOINT = 'https://api.smash.gg/gql/alpha'


class SmashGGScraper(Scraper):
    def __init__(self, session=None, api_token=None, max_requests_per_min=80, object_limit=1000):
        super(SmashGGScraper, self).__init__(session=session)
        self._client = GraphQLClient(endpoint=SMASHGG_API_ENDPOINT)
        self._client.inject_token(f'Bearer {api_token or get_config()["smashgg_api_token"]}')
        self._req_times = [0 for _ in range(max_requests_per_min)]
        self._req_idx = 0  # type: int
        self.object_limit = object_limit

    # API interaction
    def submit_request(self, query, params=None, include_metadata=False):
        """
        Submit a query request to the smash.gg API.

        :param query: The graphQL query GraphQLQuery format.
        :type query: ranking_scraper.gql_query.GraphQLQuery

        :param params: Optional - Parameters for the request.
        :type params: dict

        :param include_metadata:
        :type include_metadata: bool

        :return: The response data in dictionary format (parsed as json). The response metadata
         is not returned unless "include_metadata" is set to True. In such a case, any data is
         under the "data" key. (effectively, the response is returned as-is).
        :rtype: dict
        """
        params = params or dict()
        _l.debug(f'> Executing query "{query.query_name}".')
        result = self._execute_request(query.build(), params)  # str
        result = json.loads(result)
        # Ignore metadata and just return the requested data.
        try:
            return result if include_metadata else result["data"]
        except KeyError:
            _l.error(f'Result did not contain "data" key. Result is: {result}')
            raise

    def _execute_request(self, query, params=None, max_retries=5, initial_wait_time=1.5,
                         max_wait_time=60.0):
        """
        Executes the graphQL request with exponential back-off.

        :param query: The graphQL query in string format.
        :type query: str

        :param params: Parameters for the request. If not provided, an empty
            dict is given.
        :type params: dict

        :param max_retries: Maximum number of times to retry. Default: 5 . A value lower than 0 is
            treated as 0.
        :type max_retries: int

        :param max_wait_time: Maximum amount of time, in seconds) to wait.
            Default: 60.0 .
        :type max_wait_time: int or float

        :return: The response string.
        :rtype: str
        """
        wait_time = initial_wait_time
        max_retries = max(max_retries, 0)  # Ensure no negative value
        for attempt_nr in range(max_retries + 1):  # Initial try + max_retires
            try:
                return self._client.execute(query=query,
                                            variables=params or dict())
            except HTTPError as http_err:
                if http_err.code != 429:  # 429 = Too Many Requests
                    raise http_err
                if attempt_nr >= max_retries:  # Too many retries have failed.
                    raise http_err
                # Note: 400 (bad request) can be given to indicate too high
                # complexity for a request.
                wait_time *= 2.0
                _l.warning(f"Too many requests (429). Waiting {wait_time:.1f}"
                           f" seconds before resuming.")
                time.sleep(min(wait_time, max_wait_time))
                continue

    # Scraping methods
    def pull_event_data(self, game_code, from_dt, to_dt, countries=None):
        game = self.session.query(Game).filter(Game.code == game_code).one()
        _l.info('### Retrieving event data ###')
        countries = countries or [None]
        tour_dicts = list()
        for country_code in countries:
            tour_dicts.extend(self._get_tournament_data(game.sgg_id, from_timestamp=from_dt, to_timestamp=to_dt,
                                                        country_code=country_code))
        # 2. Check for any existing Event in database already (discard if existing).
        new_tour_dicts = self._filter_out_known_tournaments(tour_dicts)
        _l.info(f'Retrieved {len(tour_dicts)} tournaments, containing {len(new_tour_dicts)} new tournaments.')
        # 3. Create new  Event instances
        new_events = [_ for _ in itertools.chain(self._create_events_from_tournament_dict(td)
                                                 for td in new_tour_dicts)]
        self.session.add_all(new_events)
        pp(new_events)
        pp(len(new_events))
        _l.info('### Populated database with new Event instances ###')
        # self.session.commit()

    def _get_tournament_data(self, game_id, from_timestamp, to_timestamp, country_code=None):
        from_timestamp = int(from_timestamp.timestamp())
        to_timestamp = int(to_timestamp.timestamp())
        _l.info(f'Retrieving tournament data for "{country_code if country_code else "all countries"}".')
        _q = queries.get_completed_tournaments_paging(game_id=game_id, country_code=country_code,
                                                      from_date=from_timestamp, to_date=to_timestamp)
        page_info = self.submit_request(query=_q)['tournaments']['pageInfo']
        tournament_dicts = list()
        for page_nr in range(1, page_info['totalPages'] + 1):
            _l.debug(f'Retrieving page {page_nr} of {page_info["totalPages"]}')
            _q = queries.get_completed_tournaments(game_id=game_id, page_nr=page_nr, country_code=country_code,
                                                   from_date=from_timestamp, to_date=to_timestamp)
            _nodes = self.submit_request(query=_q)['tournaments']['nodes']
            tournament_dicts.extend(_nodes)
        # Sanity check: duplicate tournament retrieval check
        if len({t['id'] for t in tournament_dicts}) != len(tournament_dicts):
            _l.error(f'Duplicate tournament data retrieved! This is likely an error with the query. Skipping further '
                     f'processing of these events. (Country code: {country_code}, # of events: {len(tournament_dicts)}')
            return list()  # TODO: Perhaps safe to merge and process anyway?
        return tournament_dicts

    def _filter_out_known_tournaments(self, tournament_dicts):
        tournament_ids = [t['id'] for t in tournament_dicts]
        known_event_tournament_ids = {e.sgg_tournament_id for e in self.session.query(Event).all()}
        # TODO: Needs to check on both tournament and event id (might pass a tournament again if we do a pass on
        #  another game from the same tournament)
        new_tournament_dicts = list()
        for tour in tournament_dicts:
            if tour['id'] in known_event_tournament_ids:
                continue
            new_tournament_dicts.append(tour)
        return new_tournament_dicts

    def _create_events_from_tournament_dict(self, tournament_dict):
        new_events = list()
        pp(tournament_dict)
        for evt_data in tournament_dict['events']:
            # TODO: Filter event on gamecode (pass in param) and other criteria (isonline, etc...).
            new_event = Event(sgg_tournament_id=tournament_dict['id'],
                              sgg_event_id=evt_data['id'],
                              # TODO: rest of the values, see comment below
                              )
            new_events.append(new_event)
        """
         id = Column(Integer, primary_key=True, autoincrement=True)
    sgg_tournament_id = Column(Integer, nullable=True, index=True)  # smashgg tournament_id
    sgg_event_id = Column(Integer, nullable=True, index=True)  # smashgg event_id
    # Add other providers here (challonge, ...)
    name = Column(Text, nullable=False)
    note = Column(Text, nullable=True)  # Additional notes that can be given
    country = Column(Text, nullable=True)
    end_date = Column(DateTime, nullable=False)
    num_entrants = Column(Integer, nullable=False)
    type_code = Column(Integer, nullable=False)  # See: EventType
    format_code = Column(Integer, nullable=False)  # See: EventFormat
    state_code = Column(Integer, nullable=False)  # See: EventState"""
        return new_events
