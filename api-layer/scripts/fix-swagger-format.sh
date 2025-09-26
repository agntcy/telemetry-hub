#!/bin/bash
# Fix swagger.json formatting for CI compliance

# Check if swagger.json exists
if [ ! -f "docs/swagger.json" ]; then
    echo "swagger.json not found in docs/ directory"
    exit 1
fi

# Add trailing newline if missing
if [ -n "$(tail -c1 docs/swagger.json)" ]; then
    echo "" >> docs/swagger.json
    echo "Added trailing newline to docs/swagger.json"
else
    echo "docs/swagger.json already has trailing newline"
fi

# Optionally format the JSON for better readability
if command -v jq &> /dev/null; then
    echo "Formatting JSON with jq..."
    jq . docs/swagger.json > docs/swagger.json.tmp && mv docs/swagger.json.tmp docs/swagger.json
    echo "JSON formatted successfully"
fi
