import logging
from datetime import datetime

import click

from ranking_scraper.db import get_session, get_connection_str, create_tables, renew_tables, \
    drop_tables
from ranking_scraper.smashgg.scraper import SmashGGScraper
from ranking_scraper.smashgg.seeddb import upsert_smashgg_games
from ranking_scraper.util import configure_logging

_log = logging.getLogger('ranking_scraper.cli')

session = get_session()


@click.group()
def cli():
    pass


def _db_create():
    create_tables()
    upsert_smashgg_games()


def _db_drop():
    drop_tables()


def _db_renew():
    renew_tables()
    upsert_smashgg_games()


DB_COMMANDS = dict(create=_db_create,
                   drop=_db_drop,
                   renew=_db_renew)


@cli.command(help='''
Database commands.
'''.strip())
@click.argument('command', type=click.Choice(DB_COMMANDS.keys(), case_sensitive=False))
@click.option('--force', is_flag=True)
@click.option('--ignore-warnings', '-no-warn', 'log_level',
              flag_value=logging.ERROR,
              help='Ignore warning messages.')
@click.option('--info', 'log_level', flag_value=logging.INFO,
              help='Include informational messages.')
@click.option('--debug', 'log_level', flag_value=logging.DEBUG,
              help='Include all debugging messages.')
def db(command, force, log_level):
    log_level = log_level or logging.WARNING
    configure_logging(log_level)
    conn_str = get_connection_str()
    if not force and not click.confirm(f'Run "{command}" against "{conn_str}"?'):
        return
    _log.info(f'Running database command "{command}".')
    DB_COMMANDS[command]()


scraper_cls_map = dict(smashgg=SmashGGScraper)


# TODO: Filtering on num of participants
# TODO: Filtering on name (regex-like?)
@cli.command(help='''
    Scrape data from a tournament portal (eg. smashgg, challonge, ...)

    TODO: Rest of the docs

    By default, only errors and warnings messages are printed. Use --ignore-warning, --info, or --debug
    to set the desired verbosity level. If multiple feature flags are used, the last one specified is 
    used.
    '''.strip())
@click.argument('provider', type=click.Choice(scraper_cls_map.keys(), case_sensitive=False))
@click.option('--game',
              help='Game code to query. Example: "smash-ultimate". Case-insensitive.')
@click.option('--countries', default='',
              help='A comma-separated list of country codes. Eg. "BE,NL,FR" .')
@click.option('--from', 'from_datetime', type=click.DateTime(formats=('%Y%m%d', '%Y-%m-%d')),
              default='',
              help='Date starting from which to scrape from (inclusive)')
@click.option('--to', 'to_datetime', type=click.DateTime(formats=('%Y%m%d', '%Y-%m-%d')),
              default=datetime.utcnow(),
              help='End date (exclusive). By default is set to the current date and time.')
@click.option('--ignore-warnings', '-no-warn', 'log_level',
              flag_value=logging.ERROR,
              help='Ignore warning messages.')
@click.option('--info', 'log_level', flag_value=logging.INFO,
              help='Include informational messages.')
@click.option('--debug', 'log_level', flag_value=logging.DEBUG,
              help='Include all debugging messages.')
def scrape(provider, game, countries, from_datetime, to_datetime, log_level):
    log_level = log_level or logging.WARNING
    configure_logging(log_level)
    countries = sorted(c for c in countries.split(',') if c)
    game = game.lower()
    _log.info('Logging started')
    _log.debug(f'provider: {provider}')
    _log.debug(f'game: {game}')
    _log.debug(f'countries: {countries}')
    _log.debug(f'from_datetime: {from_datetime}')
    _log.debug(f'to_datetime: {to_datetime}')
    scraper = scraper_cls_map[provider]()
    scraper.pull_event_data(game_code=game, from_dt=from_datetime, to_dt=to_datetime,
                            countries=countries)


if __name__ == '__main__':
    cli()
