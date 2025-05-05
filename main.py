from fastmcp import FastMCP
import httpx
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from utils.selenium_utils import SeleniumUtils
from utils.run_query import run_query

from utils.config import (
    DUNE_API_KEY, BASE_URL, HEADERS,
    QUERY_TIMEOUT, STALE_DATA_THRESHOLD,
    ERROR_MESSAGES
)
from utils.exceptions import (
    DuneAPIKeyError,
    QueryExecutionError,
    QueryTimeoutError,
    NoDataError,
    SeleniumError,
)


# Load environment variables
load_dotenv()

# Initialize FastMCP
mcp = FastMCP()

# Valid chain identifiers for the trending contracts API
VALID_CHAINS = ["ethereum", "arbitrum", "optimism", "polygon", "base", "bnb", "avalanche"]

# Validate API key
if not DUNE_API_KEY:
    raise DuneAPIKeyError(ERROR_MESSAGES["no_api_key"])

# write a function and register it as a mcp tool using the @mcp.tool() decorator
@mcp.tool()
def say_hello(name: str) -> str:
    '''
    A simple greeting tool that says hello to a person.
    
    Args:
        name (str): The name of the person to greet
        
    Returns:
        str: A greeting message
        
    Example:
        >>> say_hello("Peter")
        "Hello Peter!"
    '''
    return f"Hello {name}!"

@mcp.tool()
def get_query_ids(query: str) -> List[int]:
    '''
    Get query IDs from Dune Analytics using Selenium.
    
    Args:
        query (str): The search query
        
    Returns:
        List[int]: List of query IDs found
        
    Raises:
        SeleniumError: If there is an error with Selenium operations
    '''
    selenium_utils = SeleniumUtils()
    try:
        _data = selenium_utils.get_queries_ids(query)
        if _data:
            _data = _data[0].split('/')[-1]
            return _data
        else:
            return None
    except Exception as e:
        raise SeleniumError(f"Error getting query IDs: {str(e)}")


@mcp.tool()
def get_latest_result_by_query_id(
    query_id: int,
    columns: Optional[str] = None,
    filters: Optional[str] = None,
    sort_by: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    sample_count: Optional[int] = None,
    allow_partial_results: bool = False,
    ignore_max_datapoints_per_request: bool = False
) -> List[Dict[str, Any]]:
    """
    Get the latest results for a specific query ID from Dune Analytics with advanced filtering and pagination options.
    This function automatically handles pagination to fetch all results.
    
    Args:
        query_id (int): The ID of the query to fetch results for
        columns (str, optional): Comma-separated list of column names to return. If omitted, all columns are included.
        filters (str, optional): Expression to filter out rows from the results (similar to SQL WHERE clause).
        sort_by (str, optional): Expression to define the order of results (similar to SQL ORDER BY clause).
        limit (int, optional): Maximum number of rows to return per page. Defaults to 1000 if not specified.
        offset (int, optional): Starting row number for pagination (0-based). Usually starts at 0.
        sample_count (int, optional): Number of rows to return by random sampling.
        allow_partial_results (bool): Whether to allow returning partial results if query result is too large.
        ignore_max_datapoints_per_request (bool): Whether to ignore the default 250,000 datapoints limit.
        
    Returns:
        List[Dict[str, Any]]: Query results as a list of dictionaries
        
    Raises:
        QueryExecutionError: If there is an error executing the query
        NoDataError: If no data is returned from the query
    """
    try:
        # Set default limit if not specified
        if limit is None:
            limit = 100  # Default page size
            
        # Initialize offset if not specified
        if offset is None:
            offset = 0
            
        all_results = []
        has_more_results = True
        
        while has_more_results:
            # Build query parameters
            params = {
                'limit': limit,
                'offset': offset
            }
            if columns:
                params['columns'] = columns
            if filters:
                params['filters'] = filters
            if sort_by:
                params['sort_by'] = sort_by
            if sample_count is not None:
                params['sample_count'] = sample_count
            if allow_partial_results:
                params['allow_partial_results'] = 'true'
            if ignore_max_datapoints_per_request:
                params['ignore_max_datapoints_per_request'] = 'true'

            url = f"{BASE_URL}/query/{query_id}/results"
            with httpx.Client(timeout=QUERY_TIMEOUT) as client:
                response = client.get(url, headers=HEADERS, params=params, timeout=300)
                if response.status_code == 404:
                    run_query(query_id)
                    continue
                data = response.json()
            
            # Get the current page of results
            result_data = data.get("result", {}).get("rows", [])
            execution_started_at_str = data.get("execution_started_at")
            
            if not execution_started_at_str:
                print("No execution timestamp found, running new query...")
                return run_query(query_id)
                
            print(f"Execution started at: {execution_started_at_str}")
            execution_started_at = datetime.strptime(execution_started_at_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            now = datetime.utcnow()
            delta = now - execution_started_at
            
            if not result_data or delta >= timedelta(hours=STALE_DATA_THRESHOLD):
                print("Data is stale or empty, running new query...")
                return run_query(query_id)

            # Add current page results to all results
            all_results.extend(result_data)
            
            # Check if there are more results
            next_offset = data.get("next_offset")
            if next_offset is None or len(result_data) < limit:
                has_more_results = False
            else:
                offset = next_offset
                print(f"Fetching next page of results (offset: {offset})...")

        return all_results
        
    except httpx.HTTPError as e:
        raise QueryExecutionError(f"HTTP error fetching query results: {str(e)}")
    except Exception as e:
        raise QueryExecutionError(f"Error processing query results: {str(e)}")

# trending contracts
@mcp.tool()
def get_trending_contracts(
    chain: str,
    top_n: int = 10,
    sort_by: str = "usd_value_received DESC",
    filter_days: int = None,
    token_standard: str = None
) -> List[Dict[str, Any]]:
    """
    Get trending contracts on a specific EVM chain based on activity in the last 30 days.
    
    Args:
        chain (str): The blockchain to get trending contracts for (e.g., ethereum, arbitrum, optimism)
        top_n (int, optional): Number of trending contracts to return. Defaults to 10.
        sort_by (str, optional): Field to sort the results by. Defaults to "usd_value_received DESC".
            Options include: usd_value_received, transaction_calls, unique_callers, contract_calls, unique_contract_callers
        filter_days (int, optional): Filter contracts deployed within the last X days
        token_standard (str, optional): Filter by token standard (ERC20, ERC721, ERC1155)
        
    Returns:
        List[Dict[str, Any]]: List of trending contracts with their details
        
    Raises:
        QueryExecutionError: If there is an error executing the query
        ValueError: If an invalid chain is provided
    """
    if chain.lower() not in VALID_CHAINS:
        valid_chains_str = ", ".join(VALID_CHAINS)
        raise ValueError(f"Invalid chain: {chain}. Valid chains are: {valid_chains_str}")
    
    try:
        url = f"{BASE_URL}/v1/trends/evm/contracts/{chain.lower()}"
        with httpx.Client(timeout=QUERY_TIMEOUT) as client:
            response = client.get(url, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
        
        result_data = data.get("result", {}).get("rows", [])
        
        if not result_data:
            return []
        
        # Apply filters if specified
        filtered_data = result_data
        
        if filter_days is not None:
            filtered_data = [
                contract for contract in filtered_data 
                if contract.get("deployed_days_ago", float("inf")) <= filter_days
            ]
        
        if token_standard is not None:
            filtered_data = [
                contract for contract in filtered_data 
                if contract.get("token_standard") == token_standard.upper()
            ]
        
        # Sort data if a custom sort is specified
        if sort_by:
            field, direction = sort_by.split() if " " in sort_by else (sort_by, "DESC")
            reverse = direction.upper() == "DESC"
            filtered_data.sort(
                key=lambda x: x.get(field, 0) if field in x else 0, 
                reverse=reverse
            )
        
        # Return top N results
        return filtered_data[:top_n]
        
    except httpx.HTTPError as e:
        raise QueryExecutionError(f"HTTP error fetching trending contracts: {str(e)}")
    except Exception as e:
        raise QueryExecutionError(f"Error processing trending contracts: {str(e)}")

@mcp.tool()
def analyze_trending_contracts(
    chain: str,
    analysis_type: str = "token_distribution",
    time_period: int = 30
) -> Dict[str, Any]:
    """
    Analyze trending contracts on a specific EVM chain and provide insights.
    
    Args:
        chain (str): The blockchain to analyze trending contracts for (e.g., ethereum, arbitrum)
        analysis_type (str): Type of analysis to perform:
            - "token_distribution": Distribution of token standards (ERC20, ERC721, etc.)
            - "age_distribution": Distribution of contract deployment ages
            - "value_by_age": Value received vs contract age correlation
        time_period (int): Number of days to consider for the analysis. Defaults to 30.
        
    Returns:
        Dict[str, Any]: Analysis results with statistics and insights
        
    Raises:
        QueryExecutionError: If there is an error executing the query
        ValueError: If an invalid analysis type is provided
    """
    valid_analysis_types = ["token_distribution", "age_distribution", "value_by_age"]
    if analysis_type not in valid_analysis_types:
        raise ValueError(f"Invalid analysis type: {analysis_type}. Valid types are: {', '.join(valid_analysis_types)}")
    
    # Get all trending contracts for the analysis
    contracts = get_trending_contracts(chain, top_n=100)
    
    if not contracts:
        return {"error": "No contracts found for analysis"}
    
    result = {
        "chain": chain,
        "contracts_analyzed": len(contracts),
        "analysis_type": analysis_type,
        "time_period_days": time_period,
        "generated_at": datetime.utcnow().isoformat()
    }
    
    if analysis_type == "token_distribution":
        # Analyze token standard distribution
        token_counts = {}
        for contract in contracts:
            token_standard = contract.get("token_standard", "OTHER")
            if not token_standard:
                token_standard = "OTHER"
            token_counts[token_standard] = token_counts.get(token_standard, 0) + 1
        
        total = len(contracts)
        token_distribution = {
            standard: {
                "count": count,
                "percentage": round((count / total) * 100, 2)
            }
            for standard, count in token_counts.items()
        }
        
        result["token_distribution"] = token_distribution
        
    elif analysis_type == "age_distribution":
        # Analyze contract age distribution
        age_buckets = {
            "0-7 days": 0,
            "8-30 days": 0,
            "31-90 days": 0,
            "91-180 days": 0,
            "181-365 days": 0,
            "1+ year": 0
        }
        
        for contract in contracts:
            days_ago = contract.get("deployed_days_ago", 0)
            if days_ago <= 7:
                age_buckets["0-7 days"] += 1
            elif days_ago <= 30:
                age_buckets["8-30 days"] += 1
            elif days_ago <= 90:
                age_buckets["31-90 days"] += 1
            elif days_ago <= 180:
                age_buckets["91-180 days"] += 1
            elif days_ago <= 365:
                age_buckets["181-365 days"] += 1
            else:
                age_buckets["1+ year"] += 1
        
        total = len(contracts)
        age_distribution = {
            bucket: {
                "count": count,
                "percentage": round((count / total) * 100, 2)
            }
            for bucket, count in age_buckets.items()
        }
        
        result["age_distribution"] = age_distribution
        
    elif analysis_type == "value_by_age":
        # Analyze value received vs contract age
        age_value_buckets = {
            "0-7 days": {"contracts": 0, "total_value": 0, "avg_value": 0},
            "8-30 days": {"contracts": 0, "total_value": 0, "avg_value": 0},
            "31-90 days": {"contracts": 0, "total_value": 0, "avg_value": 0},
            "91-180 days": {"contracts": 0, "total_value": 0, "avg_value": 0},
            "181-365 days": {"contracts": 0, "total_value": 0, "avg_value": 0},
            "1+ year": {"contracts": 0, "total_value": 0, "avg_value": 0}
        }
        
        for contract in contracts:
            days_ago = contract.get("deployed_days_ago", 0)
            value = contract.get("usd_value_received", 0)
            
            bucket_key = ""
            if days_ago <= 7:
                bucket_key = "0-7 days"
            elif days_ago <= 30:
                bucket_key = "8-30 days"
            elif days_ago <= 90:
                bucket_key = "31-90 days"
            elif days_ago <= 180:
                bucket_key = "91-180 days"
            elif days_ago <= 365:
                bucket_key = "181-365 days"
            else:
                bucket_key = "1+ year"
            
            age_value_buckets[bucket_key]["contracts"] += 1
            age_value_buckets[bucket_key]["total_value"] += value
        
        # Calculate averages
        for bucket in age_value_buckets:
            if age_value_buckets[bucket]["contracts"] > 0:
                age_value_buckets[bucket]["avg_value"] = round(
                    age_value_buckets[bucket]["total_value"] / age_value_buckets[bucket]["contracts"], 2
                )
        
        result["value_by_age"] = age_value_buckets
    
    return result

@mcp.tool()
def compare_trending_contracts(
    chains: List[str],
    metric: str = "usd_value_received",
    top_n: int = 5
) -> Dict[str, Any]:
    """
    Compare trending contracts across multiple EVM chains based on a specific metric.
    
    Args:
        chains (List[str]): List of blockchains to compare (e.g., ["ethereum", "arbitrum", "optimism"])
        metric (str): Metric to compare contracts by. Options:
            - "usd_value_received": USD value received in last 30 days
            - "transaction_calls": Number of transaction calls in last 30 days
            - "unique_callers": Number of unique callers in last 30 days
            - "contract_calls": Number of calls from other contracts in last 30 days
        top_n (int): Number of top contracts to retrieve for each chain. Defaults to 5.
        
    Returns:
        Dict[str, Any]: Comparison results with top contracts for each chain
        
    Raises:
        QueryExecutionError: If there is an error executing the query
        ValueError: If an invalid chain or metric is provided
    """
    valid_metrics = ["usd_value_received", "transaction_calls", "unique_callers", "contract_calls"]
    if metric not in valid_metrics:
        raise ValueError(f"Invalid metric: {metric}. Valid metrics are: {', '.join(valid_metrics)}")
    
    for chain in chains:
        if chain.lower() not in VALID_CHAINS:
            valid_chains_str = ", ".join(VALID_CHAINS)
            raise ValueError(f"Invalid chain: {chain}. Valid chains are: {valid_chains_str}")
    
    result = {
        "metric": metric,
        "top_n": top_n,
        "chains_compared": len(chains),
        "generated_at": datetime.utcnow().isoformat(),
        "comparison": {}
    }
    
    for chain in chains:
        # Get top trending contracts for this chain sorted by the specified metric
        top_contracts = get_trending_contracts(chain, top_n=top_n, sort_by=f"{metric} DESC")
        
        # Extract relevant data for comparison
        chain_data = []
        for contract in top_contracts:
            chain_data.append({
                "contract_address": contract.get("contract_address"),
                "contract_project": contract.get("contract_project"),
                "contract_name": contract.get("contract_name"),
                "deployed_days_ago": contract.get("deployed_days_ago"),
                "token_standard": contract.get("token_standard"),
                metric: contract.get(metric)
            })
        
        result["comparison"][chain] = chain_data
    
    return result

# memecoins
@mcp.tool()
def get_farcaster_memecoins(
    limit: int = 5,
    filter_clause: str = None,
    sort_by: str = "social_score desc",
    include_raw_response: bool = False
) -> Dict[str, Any]:
    """
    Get trending memecoin data from Farcaster.
    
    Args:
        limit (int, optional): Number of memecoins to retrieve, maximum 100. Default is 5.
        filter_clause (str, optional): Filter expression, similar to SQL WHERE clause. Example: "liquidity_usd > 100000".
        sort_by (str, optional): Field to sort results by, default is "social_score desc". 
            Common fields: social_score, financial_score, liquidity_usd, total_volume_week, casters, fdv, week_pnl
        include_raw_response (bool, optional): If True, returns raw API response. Default is False.
        
    Returns:
        Dict[str, Any]: Structured result with information about trending memecoins
        
    Raises:
        QueryExecutionError: If there is an error executing the query
    """
    try:
        url = f"{BASE_URL}/api/v1/farcaster/trends/memecoins"
        params = {
            "limit": min(limit, 100)  # Maximum limit of 100 according to documentation
        }
        
        # Add optional parameters if provided
        if filter_clause:
            params["filter"] = filter_clause
        if sort_by:
            params["sort"] = sort_by
        
        print(f"Fetching memecoins from: {url}")
        print(f"With params: {params}")
        
        with httpx.Client(timeout=QUERY_TIMEOUT) as client:
            response = client.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Extract data from response
        rows = data.get("result", {}).get("rows", [])
        metadata = data.get("result", {}).get("metadata", {})
        
        # Format results
        formatted_coins = []
        for coin in rows:
            formatted_coin = {
                "name": coin.get("word_raw", "Unknown"),
                "symbol": coin.get("related_symbol", None),
                "blockchain": coin.get("blockchain", "unknown"),
                "category": coin.get("meme_category", "unknown"),
                "social_score": coin.get("social_score", 0),
                "financial_score": coin.get("financial_score", 0),
                "casters": coin.get("casters", 0),
                "casts": coin.get("casts", 0),
                "channels": coin.get("channels", 0),
                "contract_address": coin.get("token_contract_address", None),
                "deployed_days_ago": coin.get("deployed_days_ago", None),
                "price": coin.get("median_price", 0),
                "market_cap": coin.get("fdv", 0),
                "liquidity": coin.get("liquidity_usd", 0),
                "volume_week": coin.get("total_volume_week", 0),
                "pnl": {
                    "day": round(coin.get("day_pnl", 0) * 100, 2),  # Convert to percentage
                    "week": round(coin.get("week_pnl", 0) * 100, 2),
                    "month": round(coin.get("month_pnl", 0) * 100, 2)
                },
                "wow_changes": {
                    "casters": coin.get("casters_wow", 0),
                    "casts": coin.get("casts_wow", 0),
                    "liquidity": coin.get("liquidity_wow", 0),
                    "volume": coin.get("total_volume_wow", 0)
                }
            }
            formatted_coins.append(formatted_coin)
        
        result = {
            "memecoins": formatted_coins,
            "count": len(formatted_coins),
            "metadata": {
                "total_count": metadata.get("total_row_count", 0),
                "columns": metadata.get("column_names", [])
            },
            "pagination": {
                "next_offset": data.get("next_offset"),
                "next_uri": data.get("next_uri")
            }
        }
        
        result = result.get("memecoins", [])
        
        return result
        
    except httpx.HTTPError as e:
        error_msg = f"HTTP error fetching Farcaster memecoins: {str(e)}"
        print(error_msg)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Error processing Farcaster memecoins: {str(e)}"
        print(error_msg)
        return {"error": error_msg}


def main():
    """
    Main entry point for the Dune Agent application.
    """
    print("Starting Dune Agent...\n")
    
    try:
        # Example 1: Get top 5 trending memecoins, sorted by social_score in descending order
        print("Example 1: Get top 5 trending memecoins, sorted by social_score in descending order:")
        memecoins = get_farcaster_memecoins(
            limit=5,
            sort_by="social_score desc"
        )
        
        if "error" not in memecoins:
            print(format_memecoin_results(memecoins))
        else:
            print(f"Error: {memecoins['error']}")
        
        # Example 2: Get top 3 memecoins with liquidity > 100000, sorted by liquidity_usd in descending order
        print("\nExample 2: Get top 3 memecoins with liquidity > 100000, sorted by liquidity_usd in descending order:")
        high_liquidity_coins = get_farcaster_memecoins(
            limit=3,
            filter_clause="liquidity_usd > 100000",
            sort_by="liquidity_usd desc"
        )
        
        if "error" not in high_liquidity_coins:
            print(high_liquidity_coins)
        else:
            print(f"Error: {high_liquidity_coins['error']}")
            
        # Example 3: Get top memecoins with best weekly performance
        print("\nExample 3: Get top memecoins with best weekly performance:")
        best_performing_coins = get_farcaster_memecoins(
            limit=3,
            sort_by="week_pnl desc"
        )
        
        if "error" not in best_performing_coins:
            print(best_performing_coins)
        else:
            print(f"Error: {best_performing_coins['error']}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
