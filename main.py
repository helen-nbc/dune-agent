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



# @mcp.tool()
# def get_top_5_chain_by_number_of_wallet() -> List[Dict[str, Any]]:
#     """
#     Get the latest results for a specific query ID from Dune Analytics.
    
#     Args:
#         query_id (int): The ID of the query to fetch results for
        
#     Returns:
#         List[Dict[str, Any]]: Query results as a list of dictionaries
        
#     Raises:
#         QueryExecutionError: If there is an error executing the query
#         NoDataError: If no data is returned from the query
#     """
#     query_id = 5055813
#     try:
#         url = f"{BASE_URL}/query/{query_id}/results"
#         with httpx.Client(timeout=QUERY_TIMEOUT) as client:
#             response = client.get(url, headers=HEADERS, timeout=300)
#             if response.status_code == 404:
#                 run_query(query_id)
#             data = response.json()
        
#         result_data = data.get("result", {}).get("rows", [])
#         execution_started_at_str = data.get("execution_started_at")
        
#         if not execution_started_at_str:
#             print("No execution timestamp found, running new query...")
#             return run_query(query_id)
            
#         print(f"Execution started at: {execution_started_at_str}")
#         execution_started_at = datetime.strptime(execution_started_at_str, "%Y-%m-%dT%H:%M:%S.%fZ")
#         now = datetime.utcnow()
#         delta = now - execution_started_at
        
#         if not result_data or delta >= timedelta(hours=STALE_DATA_THRESHOLD):
#             print("Data is stale or empty, running new query...")
#             return run_query(query_id)

#         return result_data
        
#     except httpx.HTTPError as e:
#         raise QueryExecutionError(f"HTTP error fetching query results: {str(e)}")
#     except Exception as e:
#         raise QueryExecutionError(f"Error processing query results: {str(e)}")
    
# @mcp.tool()
# def get_top_5_chain_by_trading_volume() -> List[Dict[str, Any]]:
#     """
#     Get the latest results for a specific query ID from Dune Analytics.
    
#     Args:
#         query_id (int): The ID of the query to fetch results for
        
#     Returns:
#         List[Dict[str, Any]]: Query results as a list of dictionaries
        
#     Raises:
#         QueryExecutionError: If there is an error executing the query
#         NoDataError: If no data is returned from the query
#     """
#     query_id = 5055798
#     try:
#         url = f"{BASE_URL}/query/{query_id}/results"
#         with httpx.Client(timeout=QUERY_TIMEOUT) as client:
#             response = client.get(url, headers=HEADERS, timeout=300)
#             if response.status_code == 404:
#                 run_query(query_id)
#             data = response.json()
        
#         result_data = data.get("result", {}).get("rows", [])
#         execution_started_at_str = data.get("execution_started_at")
        
#         if not execution_started_at_str:
#             print("No execution timestamp found, running new query...")
#             return run_query(query_id)
            
#         print(f"Execution started at: {execution_started_at_str}")
#         execution_started_at = datetime.strptime(execution_started_at_str, "%Y-%m-%dT%H:%M:%S.%fZ")
#         now = datetime.utcnow()
#         delta = now - execution_started_at
        
#         if not result_data or delta >= timedelta(hours=STALE_DATA_THRESHOLD):
#             print("Data is stale or empty, running new query...")
#             return run_query(query_id)

#         return result_data
        
#     except httpx.HTTPError as e:
#         raise QueryExecutionError(f"HTTP error fetching query results: {str(e)}")
#     except Exception as e:
#         raise QueryExecutionError(f"Error processing query results: {str(e)}")

def main():
    """Test the functionality of the tools."""
    try:
        # Test query execution with error handling
        test_query_id = get_query_ids("Eternal AI Daily Inferences By Chain")
        results = get_latest_result_by_query_id(test_query_id)
        print(f"Got {len(results)} results")
        
    except DuneAPIKeyError as e:
        print(f"API Key Error: {str(e)}")
    except QueryExecutionError as e:
        print(f"Query Execution Error: {str(e)}")
    except QueryTimeoutError as e:
        print(f"Query Timeout Error: {str(e)}")
    except NoDataError as e:
        print(f"No Data Error: {str(e)}")
    except SeleniumError as e:
        print(f"Selenium Error: {str(e)}")
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")

if __name__ == "__main__":
    main()
