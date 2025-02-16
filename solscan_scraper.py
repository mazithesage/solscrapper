import requests
import time
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Set
import os
from dotenv import load_dotenv

class SolscanScraper:
    def __init__(self):
        load_dotenv()
        self.base_url = "https://public-api.solscan.io"
        self.api_key = os.getenv('SOLSCAN_API_KEY')
        if not self.api_key:
            raise ValueError("SOLSCAN_API_KEY not found in .env file")
        self.headers = {
            'token': self.api_key,
            'Accept': 'application/json',
        }
        # Validate API key
        self._validate_api_key()
        self.discovered_addresses = set()

    def _validate_api_key(self):
        """
        Validate the API key by making a test request
        """
        # Try different endpoints for validation
        test_endpoints = [
            '/transaction/last',
            '/token/list',
            '/account/tokens'
        ]
        
        for endpoint in test_endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Trying to validate API key with endpoint: {url}")
                response = requests.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    print("API key validated successfully!")
                    return
                elif response.status_code == 403:
                    print(f"Access denied for endpoint {endpoint}. Trying next endpoint...")
                else:
                    print(f"Unexpected status code {response.status_code} for endpoint {endpoint}")
                    
            except requests.exceptions.RequestException as e:
                print(f"Error with endpoint {endpoint}: {str(e)}")
                continue
        
        raise ValueError("Could not validate API key with any endpoint. Please check your API key and try again.")

    def get_recent_transactions(self, limit: int = 100) -> List[Dict]:
        """
        Get recent transactions from Solscan
        """
        endpoint = f"{self.base_url}/transaction/last"
        params = {'limit': limit}
        try:
            response = requests.get(endpoint, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and 'error' in data:
                print(f"API Error: {data['error']}")
                return []
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching recent transactions: {str(e)}")
            return []

    def get_top_tokens(self, limit: int = 20) -> List[Dict]:
        """
        Get top Solana tokens by market cap
        """
        endpoint = f"{self.base_url}/token/list"
        params = {'limit': limit, 'sortBy': 'marketCap', 'sortType': 'desc'}
        try:
            response = requests.get(endpoint, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching top tokens: {str(e)}")
            return []

    def discover_addresses(self, max_addresses: int = 1000) -> Set[str]:
        """
        Discover active wallet addresses by analyzing recent transactions and token holders
        """
        print("Starting address discovery...")
        
        # Get recent transactions
        transactions = self.get_recent_transactions(limit=100)
        for tx in transactions:
            if len(self.discovered_addresses) >= max_addresses:
                break
                
            # Extract addresses from transaction
            if 'owner' in tx:
                self.discovered_addresses.add(tx['owner'])
            if 'signer' in tx:
                self.discovered_addresses.add(tx['signer'])
            if 'fromAddress' in tx:
                self.discovered_addresses.add(tx['fromAddress'])
            if 'toAddress' in tx:
                self.discovered_addresses.add(tx['toAddress'])

        # Get holders of top tokens
        top_tokens = self.get_top_tokens()
        for token in top_tokens:
            if len(self.discovered_addresses) >= max_addresses:
                break
                
            try:
                # Get token holders
                holders_endpoint = f"{self.base_url}/token/holders"
                params = {'tokenAddress': token['address'], 'limit': 50}
                response = requests.get(holders_endpoint, headers=self.headers, params=params)
                response.raise_for_status()
                holders = response.json()
                
                # Add holder addresses
                for holder in holders:
                    if len(self.discovered_addresses) >= max_addresses:
                        break
                    if 'owner' in holder:
                        self.discovered_addresses.add(holder['owner'])
                
                time.sleep(1)  # Be nice to the API
            except Exception as e:
                print(f"Error fetching holders for token {token['address']}: {str(e)}")
                continue

        print(f"Discovered {len(self.discovered_addresses)} unique addresses")
        return self.discovered_addresses

    def get_account_info(self, address: str) -> Dict:
        """
        Get detailed information about a Solana account/wallet
        """
        endpoint = f"{self.base_url}/account/{address}"
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching account info for {address}: {str(e)}")
            return {}

    def get_account_transactions(self, address: str, limit: int = 100) -> List[Dict]:
        """
        Get transaction history for a specific account
        """
        endpoint = f"{self.base_url}/account/transactions"
        params = {
            'account': address,
            'limit': limit
        }
        try:
            response = requests.get(endpoint, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching transactions for {address}: {str(e)}")
            return []

    def get_token_holdings(self, address: str) -> List[Dict]:
        """
        Get token holdings for a specific account
        """
        endpoint = f"{self.base_url}/account/tokens"
        params = {'account': address}
        try:
            response = requests.get(endpoint, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching token holdings for {address}: {str(e)}")
            return []

    def find_engaged_wallets(self, address: str) -> Dict:
        """
        Find wallets with engagement based on recent transactions and token holdings
        Returns a dictionary with engagement metrics
        """
        engagement_data = {
            'address': address,
            'is_active': False,
            'transaction_count': 0,
            'token_holdings_count': 0,
            'total_token_value': 0.0,
            'last_transaction_time': None,
            'engagement_score': 0
        }
        
        try:
            # Check recent transactions
            transactions = self.get_account_transactions(address, limit=10)
            if transactions:
                engagement_data['transaction_count'] = len(transactions)
                if transactions[0].get('blockTime'):
                    engagement_data['last_transaction_time'] = transactions[0]['blockTime']
                engagement_data['is_active'] = True
            
            # Check token holdings
            token_holdings = self.get_token_holdings(address)
            engagement_data['token_holdings_count'] = len(token_holdings)
            
            # Calculate total token value and check for significant holdings
            for token in token_holdings:
                try:
                    amount = float(token.get('amount', 0))
                    engagement_data['total_token_value'] += amount
                except (ValueError, TypeError):
                    continue
            
            # Calculate engagement score (simple metric)
            engagement_data['engagement_score'] = (
                (engagement_data['transaction_count'] * 10) +
                (engagement_data['token_holdings_count'] * 5) +
                (min(engagement_data['total_token_value'], 1000) / 10)
            )
            
            return engagement_data
        except Exception as e:
            print(f"Error analyzing engagement for {address}: {str(e)}")
            return engagement_data

    def save_to_csv(self, data: List[Dict], filename: str):
        """
        Save the scraped data to a CSV file
        """
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        print(f"Data saved to {filename}")

def main():
    scraper = SolscanScraper()

    # First, discover active wallet addresses
    print("Phase 1: Discovering active wallet addresses...")
    max_addresses = 1000  # Adjust this number based on how many addresses you want to analyze
    discovered_addresses = scraper.discover_addresses(max_addresses=max_addresses)
    
    # Convert set to list for processing
    addresses_to_scrape = list(discovered_addresses)
    
    # Optionally save discovered addresses to file
    with open('discovered_addresses.txt', 'w') as f:
        for addr in addresses_to_scrape:
            f.write(f"{addr}\n")
    
    print(f"\nSaved {len(addresses_to_scrape)} discovered addresses to 'discovered_addresses.txt'")
    print("\nPhase 2: Analyzing wallet engagement...")
    
    # Create directory for output files
    output_dir = f'solscan_engaged_wallets_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    os.makedirs(output_dir, exist_ok=True)

    all_wallet_data = []  # List to store all wallet engagement data
    processed_count = 0
    total_addresses = len(addresses_to_scrape)

    print(f"Starting to analyze {total_addresses} addresses...")

    # Process addresses in batches to manage memory
    batch_size = 50
    for i in range(0, total_addresses, batch_size):
        batch = addresses_to_scrape[i:i + batch_size]
        batch_data = []

        for address in batch:
            try:
                processed_count += 1
                print(f"Processing address {processed_count}/{total_addresses}: {address}")
                
                # Analyze wallet engagement
                engagement_data = scraper.find_engaged_wallets(address)
                
                # Only store data for engaged wallets (you can adjust this threshold)
                if engagement_data['engagement_score'] > 20:
                    batch_data.append(engagement_data)
                    
                    # Save detailed wallet data
                    wallet_info = scraper.get_account_info(address)
                    with open(f'{output_dir}/{address}_details.json', 'w') as f:
                        json.dump({
                            'engagement_metrics': engagement_data,
                            'wallet_info': wallet_info
                        }, f, indent=2)
                
                # Be polite and wait for a second to avoid overloading the API
                time.sleep(1)
                
            except Exception as e:
                print(f"Error processing address {address}: {str(e)}")
                continue
        
        # Save batch data and clear memory
        if batch_data:
            all_wallet_data.extend(batch_data)
            batch_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save batch to CSV
            batch_filename = f'{output_dir}/batch_{i//batch_size}_{batch_timestamp}.csv'
            scraper.save_to_csv(batch_data, batch_filename)
            
            print(f"Saved batch {i//batch_size + 1} with {len(batch_data)} engaged wallets")
    
    # Save final summary
    if all_wallet_data:
        # Sort by engagement score
        all_wallet_data.sort(key=lambda x: x['engagement_score'], reverse=True)
        
        # Save complete dataset
        scraper.save_to_csv(all_wallet_data, f'{output_dir}/all_engaged_wallets.csv')
        
        # Save summary statistics
        summary = {
            'total_addresses_processed': total_addresses,
            'total_engaged_wallets': len(all_wallet_data),
            'average_engagement_score': sum(w['engagement_score'] for w in all_wallet_data) / len(all_wallet_data),
            'top_engaged_wallets': all_wallet_data[:10]  # Top 10 most engaged wallets
        }
        
        with open(f'{output_dir}/analysis_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)

    print(f"\nAnalysis completed:")
    print(f"- Processed {total_addresses} addresses")
    print(f"- Found {len(all_wallet_data)} engaged wallets")
    print(f"- Results saved in {output_dir}/")


if __name__ == "__main__":
    main()
