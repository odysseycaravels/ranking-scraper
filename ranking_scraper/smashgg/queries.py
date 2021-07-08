"""
GraphQL queries in string form used by SmashGGScraper.
"""

# TODO: This is lifted from the old project. Confirm these still work (will need some rework).
from datetime import datetime

from ranking_scraper.gql_query import GraphQLQuery, StringWithoutQuotes


def get_completed_tournaments_paging(game_id: int,
                                     country_code: str = None,
                                     from_date: int = None,  # Timestamp (no floats)
                                     to_date: int = None,  # Timestamp (no floats)
                                     items_per_page=25) -> GraphQLQuery:
    query = GraphQLQuery(query_name='TournamentsPaging')
    # Field definitions
    query.f('tournaments').f('pageInfo').add_fields('totalPages', 'perPage')
    # Parameter definitions
    query.f('tournaments').add_params(query={
        'perPage': items_per_page,
        'sortBy': 'id asc',
        'filter': {
            'videogameIds': [game_id],
            'upcoming': False
        }
    })
    # Optional parameters
    if country_code:
        query.f('tournaments').params['query']['filter']['countryCode'] = country_code
    if from_date:
        query.f('tournaments').params['query']['filter']['afterDate'] = from_date
    if to_date:
        query.f('tournaments').params['query']['filter']['beforeDate'] = to_date
    return query


TOURNAMENTS_BY_COUNTRY_PAGING = """
query TournamentsByCountryPaging($countryCode: String!, $afterDate: Timestamp!, $perPage: Int!) {
  tournaments(query: {
    perPage: $perPage
    filter: {
      countryCode: $countryCode
      videogameIds: [1386]
      upcoming: false
      hasOnlineEvents: false
      afterDate: $afterDate
    }
  }) {
    pageInfo {
      totalPages
      perPage
    }
  }
}
""".strip()


def get_completed_tournaments(game_id: int,
                              page_nr: int,
                              country_code: str = None,
                              from_date: int = None,  # Timestamp (no floats)
                              to_date: int = None,  # Timestamp (no floats)
                              items_per_page=25) -> GraphQLQuery:
    query = GraphQLQuery(query_name='TournamentsData')
    # Field definitions
    query.f('tournaments').f('nodes').add_fields('id', 'name', 'countryCode', 'endAt', 'events')
    query.f('tournaments').f('nodes').f('events') \
        .add_fields('id', 'name', 'isOnline', 'numEntrants', 'state', 'type', 'videogame')
    query.f('tournaments').f('nodes').f('events').f('videogame').f('id')
    # Parameter definitions
    query.f('tournaments').add_params(query={
        'page': page_nr,
        'perPage': items_per_page,
        'sortBy': 'id asc',
        'filter': {
            'videogameIds': [game_id],
            'upcoming': False
        }
    })
    # Optional parameters
    if country_code:
        query.f('tournaments').params['query']['filter']['countryCode'] = country_code
    if from_date:
        query.f('tournaments').params['query']['filter']['afterDate'] = from_date
    if to_date:
        query.f('tournaments').params['query']['filter']['beforeDate'] = to_date
    return query


TOURNAMENTS_BY_COUNTRY = """
query TournamentsByCountry($countryCode: String!, $afterDate: Timestamp!,
                           $page: Int!, $perPage: Int!) {
  tournaments(query: {
    page: $page
    perPage: $perPage
    filter: {
      countryCode: $countryCode
      videogameIds: [1386]
      upcoming: false
      hasOnlineEvents: false
      afterDate: $afterDate
    }
  }) {
    nodes {
      id
      name
      countryCode
      endAt
      events {
        id
        name
        isOnline
        numEntrants
        state
        type
        videogame {
          id
        }
      }
    }
  }
}
""".strip()

TOURNAMENTS_ALL_PAGING = """
query TournamentsPaging($afterDate: Timestamp!, $beforeDate: Timestamp!, 
                        $perPage: Int!) {
  tournaments(query: {
    perPage: $perPage
    filter: {
      videogameIds: [1386]
      upcoming: false
      hasOnlineEvents: false
      afterDate: $afterDate
      beforeDate: $beforeDate
    }
  }) {
    pageInfo {
      totalPages
      perPage
    }
  }
}
""".strip()

TOURNAMENTS_ALL = """
query TournamentsAll($afterDate: Timestamp!, $beforeDate: Timestamp!, 
                     $page: Int!, $perPage: Int!) {
  tournaments(query: {
    page: $page
    perPage: $perPage
    filter: {
      videogameIds: [1386]
      upcoming: false
      hasOnlineEvents: false
      afterDate: $afterDate
      beforeDate: $beforeDate
    },
    sort: startAt
  }) {
    nodes {
      id
      name
      countryCode
      endAt
      events {
        id
        name
        isOnline
        numEntrants
        state
        type
        videogame {
          id
        }
      }
    }
  }
}
""".strip()


def get_event_phases(event_id: int) -> GraphQLQuery:
    query = GraphQLQuery('GetEventPhases')
    query.f('event').add_params(id=event_id) \
        .f('phases') \
        .add_fields('id', 'name', 'numSeeds', 'bracketType')
    return query


EVENT_PHASES = """
query EventPhases($eventId: ID!) {
  event(id: $eventId) {
    phases {
      id
      name
      numSeeds
      bracketType
    }
  }
}
""".strip()


def get_phase_sets_paging(phase_id: int, per_page=40) -> GraphQLQuery:
    query = GraphQLQuery('GetPhaseSetsPaging')
    query.f('phase').add_params(id=phase_id) \
        .add_fields('id', 'name', 'sets')
    # Note: SortType RECENT per docs is "sorted in order they were started".
    query.f('phase').f('sets').add_params(perPage=per_page,
                                          sortType=StringWithoutQuotes('RECENT')) \
        .f('pageInfo').f('totalPages')
    return query


PHASE_SETS_PAGING = """
query PhaseSetsPaging($phaseId: ID!, $perPage: Int!) {
  phase(id: $phaseId) {
    id
    name
    sets(
      perPage: $perPage
      sortType: CALL_ORDER
    ) {
      pageInfo {
        totalPages
      }
    }
  }
}
""".strip()


def get_phase_sets(phase_id: int, page_nr: int, per_page=40) -> GraphQLQuery:
    query = GraphQLQuery('GetPhaseSets')
    query.f('phase').add_params(id=phase_id)
    # Note: SortType RECENT per docs is "sorted in order they were started".
    query.f('phase').f('sets').add_params(page=page_nr,
                                          perPage=per_page,
                                          sortType=StringWithoutQuotes('RECENT')) \
        .f('nodes').add_fields('id', 'slots', 'startedAt')
    slots_field = query.f('phase').f('sets').f('nodes').f('slots')
    slots_field.f('standing').add_fields('placement', 'stats') \
        .f('stats').f('score').f('value')
    participants_field = slots_field.f('entrant').f('participants')
    participants_field.add_fields('gamerTag', 'verified')
    participants_field.f('user').add_fields('id').f('location').f('country')
    return query


PHASE_SETS = """
query PhaseSets($phaseId: ID!, $page: Int!, $perPage: Int!) {
  phase(id: $phaseId) {
    sets(
      page: $page
      perPage: $perPage
      sortType: CALL_ORDER
    ) {
      nodes {
        id
        slots {
          standing {
            placement
            stats {
              score {
                value
              }
            }
          }
          entrant {
            participants {
              gamerTag
              user {
                id
                location {
                  country
                }
              }
              verified
            }
          }
        }
      }
    }
  }
}
""".strip()


# TODO: Implement get player details query
def get_player_details(player_id: int):
    raise NotImplementedError('Update player tags and other relevant data')
