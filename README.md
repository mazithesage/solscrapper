# Solscan Wallet Scraper

This project provides tools to scrape and analyze Solana wallet information from Solscan. It includes two main components:
1. API-based wallet information scraper
2. Web-based transaction page scraper

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

3. Install Chrome browser (required for transaction scraping)

## Usage

### Scraping Wallet Information (API-based)

1. Edit the `addresses` list in `solscan_scraper.py` to include the Solana wallet addresses you want to analyze.

2. Run the script:
```bash
python solscan_scraper.py
```

This will create a CSV file with the scraped wallet data, including:
- Account information
- Token holdings
- Recent transactions
- Timestamp of when the data was scraped

### Scraping Transaction Page (Web-based)

To collect wallet addresses from Solscan's transaction page, use the transaction scraper with the following options:

```bash
# Default usage (scrapes 1000 addresses)
python transaction_scraper.py

# Scrape a specific number of addresses (e.g., 5000)
python transaction_scraper.py -n 5000

# Scrape unlimited addresses
python transaction_scraper.py -n 0

# Run in headless mode (no browser window)
python transaction_scraper.py --headless

# Show all available options
python transaction_scraper.py --help
```

Command-line options:
- `-n, --num_addresses`: Number of addresses to scrape (default: 1000, use 0 for unlimited)
- `--headless`: Run in headless mode without showing the browser window

The script will:
1. Scrape transactions from solscan.io/txs until the target number of addresses is reached
2. Extract unique wallet addresses from the transactions
3. Save progress periodically to avoid data loss
4. Save final results to `scraped_addresses.csv`

## Features

API Scraper:
- Fetches detailed account information
- Retrieves token holdings
- Gets recent transaction history
- Saves data in CSV format
- Implements rate limiting
- Error handling for failed requests

Transaction Scraper:
- Automated web scraping using Selenium
- Extracts wallet addresses from transaction pages
- Validates Solana addresses
- Handles pagination
- Saves unique addresses to CSV

## Note

Please be mindful of Solscan's rate limits and terms of service when using these scripts. The web scraper includes appropriate delays to avoid overwhelming the server.
