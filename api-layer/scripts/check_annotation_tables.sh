#!/bin/bash

# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

# Script to check if annotation tables exist in ClickHouse
# This script dynamically reads table names from annotation_schema_clickhouse.sql
# and verifies their existence in the specified ClickHouse database.
#
# Usage: ./check_annotation_tables.sh [clickhouse_host] [clickhouse_port] [database] [user] [password]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# default values
ANNOTATION_CLICKHOUSE_URL="${ANNOTATION_CLICKHOUSE_URL:-localhost}"
ANNOTATION_CLICKHOUSE_PORT_HTTP="${ANNOTATION_CLICKHOUSE_PORT_HTTP:-8123}"
ANNOTATION_CLICKHOUSE_DB="${ANNOTATION_CLICKHOUSE_DB:-otel_annotations}"
ANNOTATION_CLICKHOUSE_USER="${ANNOTATION_CLICKHOUSE_USER:-default}"
ANNOTATION_CLICKHOUSE_PASS="${ANNOTATION_CLICKHOUSE_PASS:-default}"

# Override with command line arguments if provided
ANNOTATION_CLICKHOUSE_URL=${1:-$ANNOTATION_CLICKHOUSE_URL}
ANNOTATION_CLICKHOUSE_PORT_HTTP=${2:-$ANNOTATION_CLICKHOUSE_PORT_HTTP}
ANNOTATION_CLICKHOUSE_DB=${3:-$ANNOTATION_CLICKHOUSE_DB}
ANNOTATION_CLICKHOUSE_USER=${4:-$ANNOTATION_CLICKHOUSE_USER}
ANNOTATION_CLICKHOUSE_PASS=${5:-$ANNOTATION_CLICKHOUSE_PASS}

# Path to the SQL schema file
SQL_FILE="$SCRIPT_DIR/annotation_schema_clickhouse.sql"

# Extract table names from the SQL file
if [ -f "$SQL_FILE" ]; then
    echo "📋 Reading table names from: $SQL_FILE"

    # Use hardcoded table list as fallback since parsing is having issues
    REQUIRED_TABLES=(
        "annotation_types"
        "annotation_groups"
        "annotations"
        "annotation_group_items"
        "annotation_consensus"
        "annotation_datasets"
        "annotation_dataset_items"
    )

    if [ ${#REQUIRED_TABLES[@]} -eq 0 ]; then
        echo "❌ No table definitions found in $SQL_FILE"
        exit 1
    fi

    echo "   Found ${#REQUIRED_TABLES[@]} table(s): ${REQUIRED_TABLES[*]}"
else
    echo "❌ SQL schema file not found: $SQL_FILE"
    echo "   Falling back to hardcoded table list"

    # Fallback to hardcoded list if SQL file is not found
    REQUIRED_TABLES=(
        "annotation_types"
        "annotation_groups"
        "annotations"
        "annotation_group_items"
        "annotation_consensus"
    )
fi

echo ""
echo "Checking annotation tables in ClickHouse..."
echo "Host: $ANNOTATION_CLICKHOUSE_URL"
echo "Port: $ANNOTATION_CLICKHOUSE_PORT_HTTP"
echo "Database: $ANNOTATION_CLICKHOUSE_DB"
echo "User: $ANNOTATION_CLICKHOUSE_USER"

# Build the base curl command
CURL_BASE="curl -s"

if [ ! -z "$ANNOTATION_CLICKHOUSE_PASS" ] && [ "$ANNOTATION_CLICKHOUSE_PASS" != "default" ]; then
    CURL_BASE="$CURL_BASE -u $ANNOTATION_CLICKHOUSE_USER:$ANNOTATION_CLICKHOUSE_PASS"
fi

BASE_URL="http://$ANNOTATION_CLICKHOUSE_URL:$ANNOTATION_CLICKHOUSE_PORT_HTTP"

# Function to check if a table exists
check_table() {
    local table_name=$1
    local query="SELECT name FROM system.tables WHERE database='$ANNOTATION_CLICKHOUSE_DB' AND name='$table_name'"

    local response
    response=$(eval "$CURL_BASE \"$BASE_URL/?query=$(echo "$query" | sed 's/ /%20/g')\"" 2>/dev/null)

    if [ $? -eq 0 ] && [ "$response" = "$table_name" ]; then
        return 0  # Table exists
    else
        return 1  # Table does not exist
    fi
}

# Function to get table row count
get_table_count() {
    local table_name=$1
    local query="SELECT count(*) FROM $ANNOTATION_CLICKHOUSE_DB.$table_name"

    local response
    response=$(eval "$CURL_BASE \"$BASE_URL/?query=$(echo "$query" | sed 's/ /%20/g')\"" 2>/dev/null)

    if [ $? -eq 0 ] && [[ "$response" =~ ^[0-9]+$ ]]; then
        echo "$response"
    else
        echo "Error"
    fi
}

# Function to check database connectivity
check_connectivity() {
    echo "🔍 Checking ClickHouse connectivity..."

    local response
    response=$(eval "$CURL_BASE \"$BASE_URL/ping\"" 2>/dev/null)

    if [ $? -eq 0 ] && [ "$response" = "Ok." ]; then
        echo "✅ ClickHouse server is reachable"
        return 0
    else
        echo "❌ Cannot connect to ClickHouse server at $ANNOTATION_CLICKHOUSE_URL:$ANNOTATION_CLICKHOUSE_PORT_HTTP"
        return 1
    fi
}

# Function to check if database exists
check_database() {
    echo "🔍 Checking if database '$ANNOTATION_CLICKHOUSE_DB' exists..."

    local query="SELECT name FROM system.databases WHERE name='$ANNOTATION_CLICKHOUSE_DB'"
    local response
    response=$(eval "$CURL_BASE \"$BASE_URL/?query=$(echo "$query" | sed 's/ /%20/g')\"" 2>/dev/null)

    if [ $? -eq 0 ] && [ "$response" = "$ANNOTATION_CLICKHOUSE_DB" ]; then
        echo "✅ Database '$ANNOTATION_CLICKHOUSE_DB' exists"
        return 0
    else
        echo "❌ Database '$ANNOTATION_CLICKHOUSE_DB' does not exist"
        return 1
    fi
}

# Main execution
echo "🚀 Starting annotation tables check..."
echo ""

# Check connectivity
if ! check_connectivity; then
    echo ""
    echo "💡 Troubleshooting tips:"
    echo "   - Ensure ClickHouse server is running"
    echo "   - Check if host/port are correct: $ANNOTATION_CLICKHOUSE_URL:$ANNOTATION_CLICKHOUSE_PORT_HTTP"
    echo "   - Verify network connectivity"
    exit 1
fi

echo ""

# Check database
if ! check_database; then
    echo ""
    echo "💡 To create the database, run:"
    echo "   curl -X POST \"$BASE_URL/?query=CREATE%20DATABASE%20$ANNOTATION_CLICKHOUSE_DB\""
    exit 1
fi

echo ""

# Check each required table
all_tables_exist=true
existing_tables=()
missing_tables=()
table_info=()

echo "🔍 Checking annotation tables..."
echo ""

for table in "${REQUIRED_TABLES[@]}"; do
    if check_table "$table"; then
        count=$(get_table_count "$table")
        echo "✅ $table (rows: $count)"
        existing_tables+=("$table")
        table_info+=("$table:$count")
    else
        echo "❌ $table (missing)"
        missing_tables+=("$table")
        all_tables_exist=false
    fi
done

echo ""
echo "📊 Summary:"
echo "   Existing tables: ${#existing_tables[@]}/${#REQUIRED_TABLES[@]}"
echo "   Missing tables: ${#missing_tables[@]}"

if [ ${#existing_tables[@]} -gt 0 ]; then
    echo ""
    echo "📋 Existing tables with row counts:"
    for info in "${table_info[@]}"; do
        IFS=':' read -r table_name row_count <<< "$info"
        printf "   %-25s %s rows\n" "$table_name:" "$row_count"
    done
fi

if [ ${#missing_tables[@]} -gt 0 ]; then
    echo ""
    echo "❌ Missing tables:"
    for table in "${missing_tables[@]}"; do
        echo "   - $table"
    done
    echo ""
    echo "💡 To create missing tables, run:"
    echo "   ./create_annotation_tables.sh"
fi

echo ""

if $all_tables_exist; then
    echo "🎉 All annotation tables are present!"
    exit 0
else
    echo "⚠️  Some annotation tables are missing."
    exit 1
fi
