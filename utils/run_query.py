import httpx
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from utils.config import (
    DUNE_API_KEY, BASE_URL, HEADERS,
    MAX_RETRIES, POLL_INTERVAL, MAX_POLL_ATTEMPTS,
    QUERY_TIMEOUT, ERROR_MESSAGES
)
from utils.exceptions import DuneAPIKeyError, QueryExecutionError, QueryTimeoutError, NoDataError

if not DUNE_API_KEY:
    raise DuneAPIKeyError(ERROR_MESSAGES["no_api_key"])

def run_query(
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
    Run a query by ID and return results from Dune Analytics with pagination support.
    
    Args:
        query_id (int): The ID of the query to run
        columns (str, optional): Comma-separated list of column names to return
        filters (str, optional): Expression to filter out rows (SQL WHERE clause style)
        sort_by (str, optional): Expression to define result order (SQL ORDER BY style)
        limit (int, optional): Maximum number of rows per page. Defaults to 1000
        offset (int, optional): Starting row number for pagination (0-based)
        sample_count (int, optional): Number of rows to return by random sampling
        allow_partial_results (bool): Allow returning partial results for large queries
        ignore_max_datapoints_per_request (bool): Ignore the 250,000 datapoints limit
        
    Returns:
        List[Dict[str, Any]]: Complete query results as a list of dictionaries
        
    Raises:
        QueryExecutionError: If there is an error executing the query
        QueryTimeoutError: If the query execution times out
        NoDataError: If no data is returned from the query
    """
    retry_count = 0
    last_error = None
    
    # Set default limit if not specified
    if limit is None:
        limit = 1000  # Default page size
        
    # Initialize offset if not specified
    if offset is None:
        offset = 0
        
    all_results = []
    has_more_results = True
    
    while retry_count < MAX_RETRIES:
        try:
            # Execute query
            url = f"{BASE_URL}/query/{query_id}/execute"
            with httpx.Client(timeout=QUERY_TIMEOUT) as client:
                execute_response = client.post(url, headers=HEADERS)
                execute_response.raise_for_status()
                execution_data = execute_response.json()
                execution_id = execution_data.get("execution_id")
                
                if not execution_id:
                    raise QueryExecutionError(ERROR_MESSAGES["no_execution_id"])

                # Poll for status
                status_url = f"{BASE_URL}/execution/{execution_id}/status"
                poll_count = 0
                
                while poll_count < MAX_POLL_ATTEMPTS:
                    status_response = client.get(status_url, headers=HEADERS)
                    status_response.raise_for_status()
                    status_data = status_response.json()
                    state = status_data.get("state")
                    
                    if state == "QUERY_STATE_COMPLETED":
                        # Fetch all pages of results
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

                            # Fetch results for current page
                            results_url = f"{BASE_URL}/execution/{execution_id}/results"
                            results_response = client.get(results_url, headers=HEADERS, params=params)
                            results_response.raise_for_status()
                            results_data = results_response.json()
                            
                            result_rows = results_data.get("result", {}).get("rows", [])
                            if result_rows:
                                all_results.extend(result_rows)
                                
                                # Check if there are more results
                                next_offset = results_data.get("next_offset")
                                if next_offset is None or len(result_rows) < limit:
                                    has_more_results = False
                                else:
                                    offset = next_offset
                                    print(f"Fetching next page of results (offset: {offset})...")
                            else:
                                has_more_results = False
                                if not all_results:  # If we have no results at all
                                    raise NoDataError(ERROR_MESSAGES["no_data"])
                                
                        return all_results
                        
                    elif state in ["QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED", "QUERY_STATE_ERROR"]:
                        raise QueryExecutionError(ERROR_MESSAGES["execution_failed"].format(state))
                        
                    elif state in ["QUERY_STATE_EXECUTING", "QUERY_STATE_PENDING"]:
                        time.sleep(POLL_INTERVAL)
                        poll_count += 1
                    else:
                        raise QueryExecutionError(ERROR_MESSAGES["unknown_state"].format(state))

                if poll_count >= MAX_POLL_ATTEMPTS:
                    raise QueryTimeoutError(ERROR_MESSAGES["timeout"])

        except (QueryExecutionError, QueryTimeoutError, NoDataError) as e:
            last_error = e
            retry_count += 1
            if retry_count < MAX_RETRIES:
                print(f"Retrying query execution (attempt {retry_count + 1}/{MAX_RETRIES})")
                time.sleep(POLL_INTERVAL)
            continue
                
        except httpx.HTTPError as e:
            last_error = QueryExecutionError(f"HTTP error running query: {str(e)}")
            retry_count += 1
            if retry_count < MAX_RETRIES:
                print(f"Retrying query execution (attempt {retry_count + 1}/{MAX_RETRIES})")
                time.sleep(POLL_INTERVAL)
            continue
            
        except Exception as e:
            raise QueryExecutionError(f"Error processing query: {str(e)}")
            
    if last_error:
        raise last_error
    return []