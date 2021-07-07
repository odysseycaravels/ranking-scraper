import copy
import itertools
import json
import logging
import time
from datetime import datetime
from urllib.error import HTTPError
from pprint import pprint as pp

import typing
from graphqlclient import GraphQLClient

from ranking_scraper.gql_query import GraphQLQuery
from ranking_scraper.model import Game, Event, EventState, EventType, EventFormat, Set
from ranking_scraper.smashgg import queries
from ranking_scraper.config import get_config
from ranking_scraper.scraper import Scraper

_l = logging.getLogger(__name__)

SMASHGG_API_ENDPOINT = 'https://api.smash.gg/gql/alpha'

# Maps smash.gg event type (int) to our internal event type (enum; backed by int).
EVENT_TYPE_ENUM_MAP = {1: EventType.SINGLES.value,
                       5: EventType.DOUBLES.value, }


class SmashGGScraper(Scraper):
    def __init__(self,
                 session=None,
                 api_token: str = None,
                 max_requests_per_min=80,
                 object_limit=1000):
        super(SmashGGScraper, self).__init__(session=session)
        self._client = GraphQLClient(endpoint=SMASHGG_API_ENDPOINT)
        self._client.inject_token(f'Bearer {api_token or get_config()["smashgg_api_token"]}')
        self._req_times = [0 for _ in range(max_requests_per_min)]
        self._req_idx = 0  # type: int
        self.object_limit = object_limit

    # API interaction
    def submit_request(self,
                       query: GraphQLQuery,
                       params: dict = None,
                       include_metadata=False) -> dict:
        """
        Submit a query request to the smash.gg API.

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

    def _execute_request(self,
                         query: str,
                         params=None,
                         max_retries: int = 5,
                         initial_wait_time: int or float = 1.5,
                         max_wait_time: int or float = 60.0):
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
    def pull_event_data(self,
                        game_code: str,
                        from_dt: datetime,
                        to_dt: datetime = None,
                        countries: typing.List[str] = None) -> typing.List[Event]:
        """
        Retrieve events for a given game in a given time frame.

        Optionally limit the query to a list of countries (defined by country codes).

        This will only retrieve tournament & their events, it will not populate the set data.

        :return: List of new events that have been added.
        """
        to_dt = to_dt or datetime.utcnow()
        countries = countries or [None]  # Note: list of None, not just list
        game = self.session.query(Game).filter(Game.code == game_code).one()
        _l.info('### Retrieving event data ###')
        found_events = list()
        for country_code in countries:
            found_events.extend(self._get_events(game,
                                                 from_dt=from_dt,
                                                 to_dt=to_dt,
                                                 country_code=country_code))
        # 2. Check for any existing Event in database already (discard if existing).
        new_events = self._filter_out_known_events(found_events)
        _l.info(f'Retrieved {len(found_events)} events, containing {len(new_events)} new events. '
                f'({len(found_events) - len(new_events)} events are already known)')
        self.session.add_all(new_events)
        _l.info('### Populated database with new Event instances ###')
        self.session.commit()
        return new_events

    def populate_event(self, event: Event):
        """
        Populates an event's set data.

        Updates the event's format and state.
        """
        if event.is_populated:
            _l.warning(f'Not populating event {event.name}. It is already populated.')
        if event.type == EventType.DOUBLES or event.type == EventType.UNKNOWN:
            error_msg = f'EventType {event.type.name} is currently not supported.'
            _l.error(error_msg)
            raise ValueError(error_msg)
        _l.debug(f'Populating event {event.name}')
        _q = queries.get_event_phases(event.sgg_event_id)
        phases_data = self.submit_request(query=_q)['event']['phases']
        event.format = _find_event_format(phases_data)  # Update event format
        set_dicts = self._get_phase_sets_data(phases_data=phases_data)
        # TODO: Continue implementation here
        pp(set_dicts)
        raise NotImplementedError('To be implemented')

    def _get_events(self, game: Game, from_dt: datetime, to_dt: datetime,
                    country_code: str = None) -> typing.List[Event]:
        """
        Fetches all events for a game from a specific time period.

        Optionally limits the retrieval to a specific country.

        :return: A dictionary of events found in all tournaments that match the given criteria.
        """
        from_dt = int(from_dt.timestamp())
        to_dt = int(to_dt.timestamp())
        _l.info(f'Retrieving tournament data for '
                f'"{country_code if country_code else "all countries"}".')
        _q = queries.get_completed_tournaments_paging(game_id=game.sgg_id,
                                                      country_code=country_code,
                                                      from_date=from_dt,
                                                      to_date=to_dt)
        page_info = self.submit_request(query=_q)['tournaments']['pageInfo']
        tournament_dicts = list()
        for page_nr in range(1, page_info['totalPages'] + 1):
            _l.info(f'Retrieving page {page_nr} of {page_info["totalPages"]}')
            _q = queries.get_completed_tournaments(game_id=game.sgg_id,
                                                   page_nr=page_nr,
                                                   country_code=country_code,
                                                   from_date=from_dt,
                                                   to_date=to_dt)
            _nodes = self.submit_request(query=_q)['tournaments']['nodes']
            tournament_dicts.extend(_nodes)
        # Sanity check: duplicate tournament retrieval check
        if len({t['id'] for t in tournament_dicts}) != len(tournament_dicts):
            _l.error(
                f'Duplicate tournament data retrieved! This is likely an error with the query. '
                f'Skipping further processing of these events. '
                f'(Country code: {country_code}, # of tournaments: {len(tournament_dicts)}')
            return list()  # TODO: Perhaps safe to merge and process anyway?
        events_list = (self._create_events_from_tournament_dict(td, game)
                       for td in tournament_dicts)
        new_events = [_ for _ in itertools.chain(*events_list)]
        return new_events

    def _create_events_from_tournament_dict(self,
                                            tournament_dict: dict,
                                            game: Game) -> typing.List[Event]:
        new_events = list()
        for evt_data in tournament_dict['events']:
            event_fullname = f'{tournament_dict["name"]} | {evt_data["name"]}'
            if evt_data['state'] != 'COMPLETED':
                _l.debug(f'SKIPPING - event not completed ({event_fullname})')
                continue
            if evt_data['isOnline'] is True:
                _l.debug(f'SKIPPING - event is online competition ({event_fullname})')
                continue
            if evt_data['videogame']['id'] != game.sgg_id:
                _l.debug(f'SKIPPING - game mismatch ({event_fullname})')
                continue
            if not _validate_event_data(evt_data,
                                        tournament_data=tournament_dict,
                                        game=game,
                                        event_fullname=event_fullname):
                continue
            event_format_code = EVENT_TYPE_ENUM_MAP.get(evt_data['type'],
                                                        EventType.UNKNOWN.value)
            new_event = Event(sgg_tournament_id=tournament_dict['id'],
                              sgg_event_id=evt_data['id'],
                              game_id=game.id,
                              name=event_fullname,
                              country=tournament_dict['countryCode'],
                              num_entrants=evt_data['numEntrants'],
                              end_date=datetime.fromtimestamp(tournament_dict['endAt']),
                              note='Added by SmashGGScraper',
                              type_code=EventFormat.UNKNOWN.value,
                              format_code=event_format_code,
                              # TODO: Some events can auto-verify?
                              state_code=EventState.UNVERIFIED.value,
                              )
            new_events.append(new_event)
        return new_events

    def _filter_out_known_events(self, events: typing.List[Event]) -> typing.List[Event]:
        new_events = list()
        tournament_ids = [evt.sgg_tournament_id for evt in events]
        known_events = self.session.query(Event) \
            .filter(Event.sgg_tournament_id.in_(tournament_ids)) \
            .all()
        known_events_ids = {(e.sgg_tournament_id, e.sgg_event_id,) for e in known_events}
        for evt in events:
            if (evt.sgg_tournament_id, evt.sgg_event_id,) in known_events_ids:
                _l.debug(f'SKIPPING - event already known ({evt.name})')
                continue
            new_events.append(evt)
        return new_events

    def _get_phase_sets_data(self, phases_data: typing.List[dict]) -> typing.List[dict]:
        all_sets_data = list()
        for phase_dict in phases_data:
            _q = queries.get_phase_sets_paging(phase_dict['id'])
            page_count = self.submit_request(query=_q)['phase']['sets']['pageInfo']['totalPages']
            for page_nr in range(1, page_count + 1):
                _l.debug(f'Retrieving sets page {page_nr} of {page_count}')
                _q = queries.get_phase_sets(phase_dict['id'], page_nr=page_nr)
                phase_sets_data = self.submit_request(query=_q)['phase']['sets']['nodes']
                all_sets_data.extend(phase_sets_data)
        return all_sets_data


def _validate_event_data(event_data, tournament_data, game, event_fullname=None):
    event_fullname = event_fullname or f'{tournament_data["name"]} / {event_data["name"]}'
    if event_data['state'] != 'COMPLETED':
        _l.debug(f'SKIPPING - event not completed ({event_fullname})')
        return False
    if event_data['isOnline'] is True:
        _l.debug(f'SKIPPING - event is online competition ({event_fullname})')
        return False
    if event_data['videogame']['id'] != game.sgg_id:
        _l.debug(f'SKIPPING - game mismatch ({event_fullname})')
        return False
    # Skip event with no or little participants
    if not event_data['numEntrants'] or event_data['numEntrants'] < 10:
        _l.debug(f'SKIPPING - no or not enough entrants ({event_fullname})')
        return False
    return True


ELIMINATION_FORMATS = {'SINGLE_ELIMINATION', 'DOUBLE_ELIMINATION', 'ROUND_ROBIN', 'SWISS'}
LADDER_FORMATS = {'MATCHMAKING'}
UNKNOWN_FORMATS = {'EXHIBITION', 'RACE', 'CUSTOM_SCHEDULE', 'ELIMINATION_ROUND'}  # Not tracked


def _find_event_format(event_phases: typing.List[dict]) -> EventFormat:
    bracket_types = set(ph['bracketType'] for ph in event_phases)
    if all(_ in ELIMINATION_FORMATS for _ in bracket_types):
        return EventFormat.ELIMINATION
    if all(_ in LADDER_FORMATS for _ in bracket_types):
        return EventFormat.LADDER
    if all(_ in UNKNOWN_FORMATS for _ in bracket_types):
        return EventFormat.UNKNOWN
    return EventFormat.UNKNOWN  # Not sure if technically possible to have a mix?
