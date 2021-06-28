"""
GraphQL queries in string form used by SmashGGScraper.
"""

# TODO: This is lifted from the old project. Confirm these still work (will need some rework).

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
