from collections import OrderedDict
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, Text, ForeignKey, Float, \
    DateTime, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import ColumnProperty, relationship


class _Base(object):
    """
    Implements common functionality for all model classes.

    1) __repr__ is implemented generically using __mapper__ column lookup.
       Note that this is intended to assist with debugging and may cause
       database calls as a result!

    2) The table name is generated based on the class name and follows the
       standard SQL naming convention. More specifically, an '_' character is
       inserted before every capital letter (except for the first) and it is
       then converted to lowercase.

       Class names are expected to follow the Python class naming convention
       (PascalCase), otherwise this may misbehave.

       Examples:
           - Car -> car
           - CarEngine -> car_engine
           - Bad_Python_Convention -> bad__python__convention  # Incorrect
           - _ImplementationClass -> __implementation_class    # Also incorrect

    See:
        http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/mixins.html#augmenting-the-base
    """
    __column_keys_cache__ = dict()
    """ Cache for the column attribute keys by class. Used by __repr__ """

    @declared_attr
    def __tablename__(cls):
        """ Table name generation. """
        cls_name = cls.__name__
        table_name = cls_name[0]
        for c in cls_name[1:]:
            if c.isupper():
                table_name += '_'
            table_name += c
        return table_name.lower()

    def __repr__(self):
        """
        Representative string generated from column definitions (and values).

        Only column properties (not relations) are included in the string.

        Column names are cached after the first call.

        Note that this may cause additional calls to the database and should
        only be used for debugging!
        """
        if self.__class__ not in self.__column_keys_cache__:
            keys = [_prop.key
                    for _prop in self.__mapper__.iterate_properties
                    if isinstance(_prop, ColumnProperty)]
            self.__column_keys_cache__[self.__class__] = keys
        keys = sorted(self.__column_keys_cache__[self.__class__])
        values = [getattr(self, k) for k in keys]
        prop_values = OrderedDict(zip(keys, values))
        prop_strings = [f"{k}='{v}'" for k, v in prop_values.items()]
        props = ", ".join(prop_strings)
        return f"<{self.__class__.__name__}({props})>"


Base = declarative_base(cls=_Base)


class EventState(Enum):
    UNVERIFIED = 0
    VERIFIED_DATA_INCOMPLETE = -1  # Some set or player data is missing. Usually manually fixable.
    VERIFIED_MANUAL_OK = 10  # Manually set as complete.
    VERIFIED_OK = 100  # Event set data is fully complete.
    IGNORE = -99  # Event is not suitable. Eg. A squad strike event


class EventType(Enum):
    UNKNOWN = 0
    SINGLES = 1
    DOUBLES = 2


class EventFormat(Enum):
    UNKNOWN = 0
    ELIMINATION = 1  # Includes single + double elim, as well as round-robin
    LADDER = 2


class Game(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    sgg_id = Column(Integer, nullable=True, index=True)
    code = Column(Text, nullable=False)  # TODO: validate: no spaces, all lower
    display_name = Column(Text, nullable=False)

    events = relationship('Event', back_populates='game')


class Event(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    sgg_tournament_id = Column(Integer, nullable=True, index=True)  # smashgg tournament_id
    sgg_event_id = Column(Integer, nullable=True, index=True)  # smashgg event_id
    # Add other providers here (challonge, ...)
    name = Column(Text, nullable=False)
    created_on = Column("created_on", TIMESTAMP, nullable=False, default=datetime.utcnow)
    note = Column(Text, nullable=True)  # Additional notes that can be given
    country = Column(Text, nullable=True)
    end_date = Column(DateTime, nullable=False)
    num_entrants = Column(Integer, nullable=False)
    type_code = Column(Integer, nullable=False)  # See: EventType
    format_code = Column(Integer, nullable=False)  # See: EventFormat
    state_code = Column(Integer, nullable=False)  # See: EventState

    game_id = Column(Integer, ForeignKey('game.id'), nullable=False)
    game = relationship("Game", back_populates="events")

    sets = relationship("Set", back_populates="event")

    @property
    def type(self) -> EventType:
        return EventType(self.type_code)

    @property
    def format(self) -> EventFormat:
        return EventFormat(self.format_code)

    @format.setter
    def format(self, new_format: EventFormat):
        self.format_code = new_format.value

    @property
    def state(self) -> EventState:
        return EventState(self.state_code)

    @state.setter
    def state(self, new_state: EventState):
        self.state_code = new_state.value

    @property
    def is_populated(self):
        """ Whether the sets from this event have been retrieved. """
        return len(self.sets) > 0

    @property
    def verified_sets(self):
        """ Return all the sets of this event that are verified. """
        return [set_ for set_ in self.sets if set_.is_verified]


# TODO: Need a way to merge player instances + a way to track that so it doesn't get re-scraped.
#  Useful for: Multiple accounts for 1 person. To verify an anon entry.
class Player(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    sgg_id = Column(Integer, nullable=True, index=True)
    name = Column(Text, nullable=False)
    country = Column(Text, nullable=True)

    won_sets = relationship('Set',
                            foreign_keys="Set.winning_player_id",
                            back_populates="winning_player")

    lost_sets = relationship('Set',
                             foreign_keys="Set.losing_player_id",
                             back_populates="losing_player")

    @property
    def sets(self):
        """
        Retrieves both winning and losing sets.

        Note that this collection is read-only! Additions to this collection
        will not be persisted (unless of course it has the necessary references
        already).
        """
        return self.won_sets + self.lost_sets

    @property
    def verified_sets(self):
        """ Returns all sets that are verified. """
        return [s for s in self.sets if s.is_verified]

    @property
    def is_anonymous(self):
        """
        If the player has no external IDs at all.

        Since there is no way to be sure, a lot of duplicate names may exist
        under different anonymous user (1 per event). This does NOT mean
        they don't have an account, but merely that the event these results are
        from did not have the player as a verified attendee.

        Unfortunately, because of the large data set there are bound to many
        name clashes that we cannot resolve automatically.
        """
        return not any([self.sgg_id])  # Add challonge, etc if we add them later


# TODO: Set currently assumes 1v1 - should be able to support teams so we can do team ratings
class Set(Base):
    """
    A set between two players in a Event.

    The round specified the order in which sets must be processed.

    For double elimination, these are all winner side matches followed by all
    loser side matches and finalized with grand finals.

    For round robin or swiss, these are ???

    TODO: Process at the same time (batch change) or figure out some order?

    A negative score indicates a DQ.
    """
    id = Column(Integer, primary_key=True)
    sgg_id = Column(Integer, nullable=True, index=True)  # smashgg set_id
    created_on = Column("created_on", TIMESTAMP, nullable=False, default=datetime.utcnow)
    order = Column(Integer, nullable=False)  # Order index

    event_id = Column(Integer, ForeignKey('event.id'), nullable=False)
    event = relationship("Event", back_populates="sets")

    winning_player_id = Column(Integer, ForeignKey('player.id'), nullable=False)
    winning_player = relationship("Player", foreign_keys=[winning_player_id],
                                  back_populates="won_sets")
    winning_score = Column(Integer, nullable=False)
    winning_player_is_verified = Column(Boolean, nullable=False)

    losing_player_id = Column(Integer, ForeignKey('player.id'), nullable=False)
    losing_player = relationship("Player", foreign_keys=[losing_player_id],
                                 back_populates="lost_sets")
    losing_score = Column(Integer, nullable=False)
    losing_player_is_verified = Column(Boolean, nullable=False)

    @property
    def is_verified(self):
        """ Whether both players are verified and non-anonymous entrants. """
        return self.winning_player_is_verified and \
               not self.winning_player.is_anonymous and \
               self.losing_player_is_verified and \
               not self.losing_player.is_anonymous


class Ranking(Base):
    """ A ranking system and its associated configurations. """
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)  # Display name for a ranking
    algorithm = Column(Text, nullable=False)  # Eg.: elo, glicko, ...

    algorithm_params = Column(JSONB, default=dict)  # Non-mutable. Must assign to field.
    # Values in "algorithm_params" depends on algorithm used.


class RankingPeriod(Base):
    """
    Ranking data at a specific point in time.

    These serve both historical views and as a cache of intermediate results.
    """
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)  # Display name for a ranking
    start_date = Column(DateTime, nullable=False)  # Date the ranking period started
    end_date = Column(DateTime, nullable=False)  # Date the ranking period ended

    ranking_id = Column(Integer, ForeignKey('ranking.id'), nullable=True)
    ranking = relationship("Ranking")

    previous_period_id = Column(Integer, ForeignKey('ranking_period.id'), nullable=True)
    previous_period = relationship("RankingPeriod")

    # TODO: start_date can be inferred from previous ranking?
    # TODO: name can be generated as "ranking.name [start_date - end_date]".


class PlayerRating(Base):
    """
    A player's score and metadata at a given ranking's time.

    Because different algorithms may require different forms of metadata, it is
    exposed a JSONB field.
    """
    id = Column(Integer, primary_key=True, autoincrement=True)
    rating = Column(Float, nullable=False)
    # Algorithm-specific metadata. Eg. K-values for ELO. RD for glicko, etc...
    algorithm_params = Column(JSONB, default=dict)  # Non-mutable. Must assign to field.

    ranking_period_id = Column(Integer, ForeignKey('ranking_period.id'), nullable=True)
    ranking_period = relationship("RankingPeriod")
