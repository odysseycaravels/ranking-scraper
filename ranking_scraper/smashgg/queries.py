"""
GraphQL queries in string form used by SmashGGScraper.
"""

# TODO: This is lifted from the old project. Confirm these still work (will need some rework).
from ranking_scraper.gql_query import GraphQLQuery


def get_completed_tournaments_paging(game_id, country_code=None, from_date=None, to_date=None,
                                     items_per_page=25):
    """
    :param game_id: Smash.gg game id

    :param country_code: Country code (eg. BE, FR, ...)

    :param from_date: Datetime UNIX timestamp as int. (This particular api does not accept float timestamps).
    :type from_date: int

    :param to_date: Datetime UNIX timestamp as int. (This particular api does not accept float timestamps).
    :type to_date: int

    :param items_per_page: Number of items to retrieve per page.

    :rtype: GraphQLQuery
    """
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


def get_completed_tournaments(game_id, page_nr, country_code=None, from_date=None, to_date=None,
                              items_per_page=25):
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
