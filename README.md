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
