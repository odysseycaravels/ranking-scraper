# ranking-scraper
Data scraping workers. Designed to be run on-demand or at intervals.

## Setup

0. Create a virtual environment
0. Install requirements (`pip install requirements.txt`)
0. Create configuration file

## Usage

A configuration file must be defined before this is usable.

This can be specified using `ODC_RATINGS_CONFIG` or by creating a
`config.json` in the working directory. See example_config.json in
this repository for the expected structure. 

CLI: `python -m ranking_scraper.cli --help`

## Development

Vagrantfile for database in ranking-api project.

## TODOs & Goals

* [TODO] Move SQLAlchemy model to a separate package (shared between ranking-api and ranking-scraper)
* [FEATURE] Scrape smashgg tournament data
  - Filtering by: Game type, start date, end date, country, online/offline, 
    name (regex matching?).
  - Split up tournament events & phases into unique Events
    - text

## License

MIT License