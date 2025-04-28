find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf
rm -rf mcp-agent.zip
zip -r mcp-agent.zip utils main.py Dockerfile requirements.txt