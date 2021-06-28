from ranking_scraper.db import get_session

from ranking_scraper.model import Game

import logging

_log = logging.getLogger(__name__)

GAME_TO_ID_MAP = {
    "smash-ultimate": 1386,
    "smash-melee": 1,
}


def upsert_smashgg_games():
    _log.info('Upserting smash.gg Game IDs.')
    session = get_session()
    games = session.query(Game) \
        .filter(Game.code.in_(GAME_TO_ID_MAP.keys())) \
        .all()
    # 1. Update sgg_id for found games
    for g in games:  # type: Game
        if g.sgg_id == GAME_TO_ID_MAP[g.code]:
            _log.info(f'Skipping {g} (sgg_id already set).')
            continue
        _log.info(f'Updating sgg_id for {g}.')
        g.sgg_id = GAME_TO_ID_MAP[g.code]
    # 2. Create missing Game instances
    known_codes = [g.code for g in games]
    for game_code in (code for code in GAME_TO_ID_MAP.keys() if code not in known_codes):
        new_game = Game(code=game_code, display_name=game_code, sgg_id=GAME_TO_ID_MAP[game_code])
        _log.info(f'Adding new game for {game_code}.')
        session.add(new_game)
    session.commit()
