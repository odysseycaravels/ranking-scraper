import json
import logging
import time
from urllib.error import HTTPError

from graphqlclient import GraphQLClient

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

        :param query: The graphQL query in string format.
        :type query: str

        :param params: Optional - Parameters for the request.
        :type params: dict

        :param include_metadata:
        :type include_metadata: bool

        :return: The response data in dictionary format (parsed as json). The response metadata
         is not returned unless "include_metadata" is set to True.
        :rtype: dict
        """
        params = params or dict()
        _l.debug(f'> Executing query (page {params.get("page", 1)})')
        result = self._execute_request(query, params)  # str
        result = json.loads(result)
        # Ignore metadata and just return the requested data.
        try:
            return result["data"]
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
    def pull_tournaments(self, game_code, from_dt, to_dt, countries=None,
                         skip_retrieving_sets=False):
        _l.info('1. Retrieve tournament paging info')
        _l.info('   Note -- If a lot of tournaments are to be retrieved. Split up into multiple '
                'database transaction. (1 per page seems like a sane amount)')
        _l.info('2. Retrieve tournament data')
        _l.info('3. For each tournament, retrieve events and phases')
        _l.info('4. For each event')
        _l.info('    * Create Event entry')
        _l.info('    * Retrieve sets unless "skip_retrieving_sets" is False.')
        _l.info('5. Commit database transaction')
