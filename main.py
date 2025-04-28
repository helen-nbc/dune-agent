from fastmcp import FastMCP
import httpx
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from utils.selenium_utils import SeleniumUtils

from utils.config import (
    DUNE_API_KEY, BASE_URL, HEADERS,
    MAX_RETRIES, POLL_INTERVAL, MAX_POLL_ATTEMPTS,
    QUERY_TIMEOUT, STALE_DATA_THRESHOLD,
    ERROR_MESSAGES
)
from utils.exceptions import (
    DuneAPIKeyError,
    QueryExecutionError,
    QueryTimeoutError,
    NoDataError,
    SeleniumError
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
def get_latest_result(query_id: int) -> List[Dict[str, Any]]:
    """
    Get the latest results for a specific query ID from Dune Analytics.
    
    Args:
        query_id (int): The ID of the query to fetch results for
        
    Returns:
        List[Dict[str, Any]]: Query results as a list of dictionaries
        
    Raises:
        QueryExecutionError: If there is an error executing the query
        NoDataError: If no data is returned from the query
    """
    try:
        url = f"{BASE_URL}/query/{query_id}/results"
        with httpx.Client(timeout=QUERY_TIMEOUT) as client:
            response = client.get(url, headers=HEADERS, timeout=300)
            if response.status_code == 404:
                run_query(query_id)
            data = response.json()
        
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

        return result_data
        
    except httpx.HTTPError as e:
        raise QueryExecutionError(f"HTTP error fetching query results: {str(e)}")
    except Exception as e:
        raise QueryExecutionError(f"Error processing query results: {str(e)}")

@mcp.tool()
def run_query(query_id: int) -> List[Dict[str, Any]]:
    """
    Run a query by ID and return results from Dune Analytics.
    
    Args:
        query_id (int): The ID of the query to run
        
    Returns:
        List[Dict[str, Any]]: Query results as a list of dictionaries
        
    Raises:
        QueryExecutionError: If there is an error executing the query
        QueryTimeoutError: If the query execution times out
        NoDataError: If no data is returned from the query
    """
    retry_count = 0
    last_error = None
    
    while retry_count < MAX_RETRIES:
        try:
            # Execute query
            url = f"{BASE_URL}/query/execute/{query_id}"
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
                        # Fetch results
                        results_url = f"{BASE_URL}/execution/{execution_id}/results"
                        results_response = client.get(results_url, headers=HEADERS)
                        results_response.raise_for_status()
                        results_data = results_response.json()
                        
                        result_rows = results_data.get("result", {}).get("rows", [])
                        if result_rows:
                            return result_rows
                        raise NoDataError(ERROR_MESSAGES["no_data"])
                        
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

def main():
    """Test the functionality of the tools."""
    try:
        # Test query execution with error handling
        test_query_id = get_query_ids("Eternal AI Daily Inferences By Chain")
        results = get_latest_result(test_query_id)
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
