# A Coding Template

## How to write an MCP agent?

1. follow the instructions in the main.py file 
2. write functions and register them to mcp.tool(), e.g:

```python
@mcp.tool()
def your_function(arg_1: str, arg_2: str) -> str:
.... 
```

3. when everything is ready, update the `requirements.txt`, make sure all needed dependencies are included. Then, use pack.sh to zip the source code (`bash pack.sh`). Finally, submit the output file `mcp-agent.zip` to create (or update) the agent. 


## How to build docker 
```bash
# Build image
docker build -t dune-agent .

# Run container
docker run -d --name dune-agent dune-agent
```

# Dune Agent

This agent provides tools for interacting with Dune Analytics data through the Dune API.

## Features

- **Query Execution**: Run SQL queries on Dune Analytics and get the results
- **Trending Contracts**: Get and analyze trending contracts from multiple EVM chains
- **Chain Analysis**: Analyze and compare blockchain activity across different networks

## Setup

1. Clone this repository
2. Create a `.env` file with your Dune API key:
   ```
   DUNE_API_KEY=your_api_key_here
   ```
3. Install dependencies: `pip install -r requirements.txt`
4. Run the agent: `python main.py`

## Usage

### Trending Contracts API Features

The agent provides several tools for working with Dune's trending contracts API:

#### Get Trending Contracts

Fetch trending contracts from any EVM chain based on recent activity:

```python
# Get top 10 trending contracts on Ethereum by value received
contracts = get_trending_contracts(
    chain="ethereum", 
    top_n=10,
    sort_by="usd_value_received DESC"
)

# Filter for recently deployed NFT contracts (ERC721)
nft_contracts = get_trending_contracts(
    chain="optimism",
    token_standard="ERC721",
    filter_days=30  # Deployed in last 30 days
)
```

#### Analyze Contract Trends

Analyze contract trends by token standard, age distribution, or value correlation:

```python
# Analyze token standard distribution on Arbitrum
token_analysis = analyze_trending_contracts(
    chain="arbitrum",
    analysis_type="token_distribution"
)

# See how contract age correlates with value on Polygon
age_value = analyze_trending_contracts(
    chain="polygon",
    analysis_type="value_by_age"
)
```

#### Compare Across Chains

Compare contract activity across multiple chains:

```python
# Compare top contracts across multiple chains by transaction volume
comparison = compare_trending_contracts(
    chains=["ethereum", "arbitrum", "optimism"],
    metric="transaction_calls",
    top_n=5
)
```



### Farcaster Memecoins API

Use the new tool to access the trending memecoin data on Farcaster:

```python
# Get the top 5 trending memecoins, sorted by social_score descending
memecoins = get_farcaster_memecoins(
limit=5,
sort_by="social_score desc"
)

# Get the top 3 memecoins with liquidity > 100000, sorted by liquidity_usd descending
high_liquidity_coins = get_farcaster_memecoins(
limit=3,
filter_clause="liquidity_usd > 100000",
sort_by="liquidity_usd desc"
)

# Get the top memecoins with the best weekly performance
best_performing_coins = get_farcaster_memecoins(
limit=3,
sort_by="week_pnl desc"
)

```
#### Important data fields important

Memecoin data from the Dune API includes the following important information:

- **Basic information**: `word_raw` (name), `related_symbol` (symbol), `blockchain`, `meme_category` (category)
- **Social metrics**: `social_score`, `casters` (users), `casts` (posts), `channels` (channels)
- **Financial metrics**: `financial_score`, `median_price` (price), `liquidity_usd` (liquidity), `fdv` (capitalization)
- **Performance**: `day_pnl`, `week_pnl`, `month_pnl` (return by day/week/month)
- **Last week comparison**: `casters_wow`, `liquidity_wow`, `total_volume_wow` (changed from last week)

#### Filtering and sorting options

- **Filtering data**: Use `filter_clause` with syntax similar to WHERE in SQL
- **Sort**: Use `sort_by` with syntax "field_name direction" (e.g. "social_score desc")
- **Limit**: Use `limit` to limit the number of results (max 100)

#### Pagination

This API supports pagination to retrieve more data. Pagination information is returned in the results and can be used for subsequent requests.

Each of these tools provides rich data that can be used for:
- Tracking social engagement trends on Farcaster
- Monitoring memecoin activity across the ecosystem
- Identifying popular channels and conversation topics
- Analyzing relationships between social engagement and onchain activity
