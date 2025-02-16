# Solscan Wallet Scraper

This script allows you to scrape wallet information from Solscan, including account details, token holdings, and transaction history.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root and add your Solscan API key:
```
SOLSCAN_API_KEY=your_api_key_here
```

You can obtain a Solscan API key by registering at https://public-api.solscan.io/

## Usage

1. Edit the `addresses` list in `solscan_scraper.py` to include the Solana wallet addresses you want to scrape.

2. Run the script:
```bash
python solscan_scraper.py
```

The script will create a CSV file with the scraped data, including:
- Account information
- Token holdings
- Recent transactions
- Timestamp of when the data was scraped

## Features

- Fetches detailed account information
- Retrieves token holdings
- Gets recent transaction history
- Saves data in CSV format
- Implements rate limiting to respect API constraints
- Error handling for failed requests

## Note

Please be mindful of Solscan's API rate limits and terms of service when using this script.
