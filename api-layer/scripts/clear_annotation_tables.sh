#!/bin/bash

# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

# clear_annotation_tables.sh - Remove all content from annotation tables
#
# This script truncates all annotation tables, removing all data while preserving
# the table structure. Optionally, it can completely drop the tables.
# This is useful for:
# - Cleaning up test data
# - Resetting annotation database for fresh start
# - Development environment cleanup
# - Complete table removal for schema changes
#
# Usage:
#   ./scripts/clear_annotation_tables.sh [OPTIONS] [host] [port] [database] [user] [password]
#
# Options:
#   -f, --force-drop    Drop tables completely instead of just truncating content
#   -h, --help         Show this help message
#
# Examples:
#   ./scripts/clear_annotation_tables.sh                              # Truncate tables only
#   ./scripts/clear_annotation_tables.sh -f                           # Drop tables completely
#   ./scripts/clear_annotation_tables.sh localhost 8123 annotations_db default
#   ./scripts/clear_annotation_tables.sh -f localhost 8123 annotations_db default mypassword

set -e

# Parse command line arguments
FORCE_DROP=false

# Function to show help
show_help() {
    echo "clear_annotation_tables.sh - Remove all content from annotation tables"
    echo ""
    echo "Usage:"
    echo "  ./scripts/clear_annotation_tables.sh [OPTIONS] [host] [port] [database] [user] [password]"
    echo ""
    echo "Options:"
    echo "  -f, --force-drop    Drop tables completely instead of just truncating content"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/clear_annotation_tables.sh                              # Truncate tables only"
    echo "  ./scripts/clear_annotation_tables.sh -f                           # Drop tables completely"
    echo "  ./scripts/clear_annotation_tables.sh localhost 8123 annotations_db default"
    echo "  ./scripts/clear_annotation_tables.sh -f localhost 8123 annotations_db default mypassword"
    echo ""
    exit 0
}

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--force-drop)
            FORCE_DROP=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        -*)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
        *)
            # Non-option argument, break to handle positional parameters
            break
            ;;
    esac
done

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

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to execute ClickHouse query
execute_query() {
    local query="$1"
    local description="$2"

    echo -e "${BLUE}Executing: ${description}${NC}"

    if [ -n "$ANNOTATION_CLICKHOUSE_PASS" ]; then
        curl -s -X POST "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?database=${ANNOTATION_CLICKHOUSE_DB}&user=${ANNOTATION_CLICKHOUSE_USER}&password=${ANNOTATION_CLICKHOUSE_PASS}" \
             --data-binary "$query" \
             -H "Content-Type: text/plain"
    else
        curl -s -X POST "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?database=${ANNOTATION_CLICKHOUSE_DB}&user=${ANNOTATION_CLICKHOUSE_USER}" \
             --data-binary "$query" \
             -H "Content-Type: text/plain"
    fi
}

# Function to check if table exists and get row count
check_table() {
    local table="$1"
    echo -e "${BLUE}Checking table: ${table}${NC}"

    # Check if table exists
    local exists_query="SELECT count() FROM system.tables WHERE database = '${ANNOTATION_CLICKHOUSE_DB}' AND name = '${table}'"
    local exists_result

    if [ -n "$ANNOTATION_CLICKHOUSE_PASS" ]; then
        exists_result=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}&password=${ANNOTATION_CLICKHOUSE_PASS}" --data-binary "$exists_query")
    else
        exists_result=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}" --data-binary "$exists_query")
    fi

    if [ "$exists_result" = "1" ]; then
        # Get row count before clearing
        local count_query="SELECT count() FROM ${ANNOTATION_CLICKHOUSE_DB}.${table}"
        local count_result

        if [ -n "$ANNOTATION_CLICKHOUSE_PASS" ]; then
            count_result=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}&password=${ANNOTATION_CLICKHOUSE_PASS}" --data-binary "$count_query")
        else
            count_result=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}" --data-binary "$count_query")
        fi

        echo -e "  ${GREEN}✓${NC} Table exists with ${count_result} rows"
        return 0
    else
        echo -e "  ${YELLOW}⚠${NC} Table does not exist"
        return 1
    fi
}

# Function to confirm action
confirm_action() {
    if [ "$FORCE_DROP" = true ]; then
        echo -e "${RED}⚠ WARNING: This will COMPLETELY DROP all annotation tables!${NC}"
        echo -e "${RED}⚠ Table structures will be permanently deleted!${NC}"
        echo -e "${RED}⚠ This action cannot be undone!${NC}"
        echo ""
        echo "Target database: ${ANNOTATION_CLICKHOUSE_DB} at ${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}"
        echo ""
        echo "Tables that will be DROPPED:"
        for table in "${existing_tables[@]}"; do
            echo "  - $table"
        done
        echo ""
        read -p "Are you sure you want to DROP these tables? (yes/no): " -r
    else
        echo -e "${YELLOW}⚠ WARNING: This will remove ALL data from annotation tables!${NC}"
        echo -e "${YELLOW}⚠ This action cannot be undone!${NC}"
        echo ""
        echo "Target database: ${ANNOTATION_CLICKHOUSE_DB} at ${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}"
        echo ""
        read -p "Are you sure you want to continue? (yes/no): " -r
    fi
    echo ""

    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo -e "${RED}Operation cancelled.${NC}"
        exit 1
    fi
}

echo "======================================================"
echo "       Clear Annotation Tables Script"
echo "======================================================"
echo ""
if [ "$FORCE_DROP" = true ]; then
    echo -e "${RED}MODE: DROP TABLES${NC} (tables will be completely removed)"
else
    echo -e "${BLUE}MODE: TRUNCATE TABLES${NC} (tables will be emptied but preserved)"
fi
echo ""
echo "Connection details:"
echo "  Host: $ANNOTATION_CLICKHOUSE_URL"
echo "  Port: $ANNOTATION_CLICKHOUSE_PORT_HTTP"
echo "  Database: $ANNOTATION_CLICKHOUSE_DB"
echo "  User: $ANNOTATION_CLICKHOUSE_USER"
echo ""

# Test ClickHouse connectivity
echo -e "${BLUE}Testing ClickHouse connectivity...${NC}"
if [ -n "$ANNOTATION_CLICKHOUSE_PASS" ]; then
    PING_RESULT=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/ping" --user "${ANNOTATION_CLICKHOUSE_USER}:${ANNOTATION_CLICKHOUSE_PASS}" || echo "FAILED")
else
    PING_RESULT=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/ping" || echo "FAILED")
fi

if [ "$PING_RESULT" != "Ok." ]; then
    echo -e "${RED}✗ Failed to connect to ClickHouse at ${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}${NC}"
    echo "Please check your connection parameters and ensure ClickHouse is running."
    exit 1
fi
echo -e "${GREEN}✓ ClickHouse connection successful${NC}"
echo ""

# Check database exists
echo -e "${BLUE}Checking database existence...${NC}"
DB_CHECK_QUERY="SELECT count() FROM system.databases WHERE name = '${ANNOTATION_CLICKHOUSE_DB}'"
if [ -n "$ANNOTATION_CLICKHOUSE_PASS" ]; then
    DB_EXISTS=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}&password=${ANNOTATION_CLICKHOUSE_PASS}" --data-binary "$DB_CHECK_QUERY")
else
    DB_EXISTS=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}" --data-binary "$DB_CHECK_QUERY")
fi

if [ "$DB_EXISTS" != "1" ]; then
    echo -e "${RED}✗ Database '${ANNOTATION_CLICKHOUSE_DB}' does not exist${NC}"
    echo "Please create the database first or check the database name."
    exit 1
fi
echo -e "${GREEN}✓ Database '${ANNOTATION_CLICKHOUSE_DB}' exists${NC}"
echo ""

# List of annotation tables to clear (dynamically read from schema file)
SQL_FILE="$SCRIPT_DIR/annotation_schema_clickhouse.sql"

if [ -f "$SQL_FILE" ]; then
    echo "Reading table names from: $SQL_FILE"

    # Extract table names using grep and awk
    # Look for "CREATE TABLE IF NOT EXISTS table_name" or "CREATE TABLE table_name"
    mapfile -t TABLES < <(grep -i "CREATE TABLE" "$SQL_FILE" | \
        sed -E 's/.*CREATE TABLE (IF NOT EXISTS )?([a-zA-Z_][a-zA-Z0-9_]*).*/\2/' | \
        sort)

    if [ ${#TABLES[@]} -eq 0 ]; then
        echo "❌ No table definitions found in $SQL_FILE"
        echo "   Falling back to hardcoded table list"
        # Fallback to hardcoded list including new dataset tables
        TABLES=(
            "annotation_consensus"
            "annotation_group_items"
            "annotations"
            "annotation_groups"
            "annotation_types"
            "annotation_datasets"
            "annotation_dataset_items"
        )
    else
        echo "   Found ${#TABLES[@]} table(s): ${TABLES[*]}"
        # Reverse the order for proper dependency handling when dropping
        # (dataset items before datasets, etc.)
        reversed_tables=()
        for ((i=${#TABLES[@]}-1; i>=0; i--)); do
            reversed_tables+=("${TABLES[i]}")
        done
        TABLES=("${reversed_tables[@]}")
    fi
else
    echo "❌ SQL schema file not found: $SQL_FILE"
    echo "   Using hardcoded table list including dataset tables"
    # Hardcoded list including new dataset tables (in reverse dependency order)
    TABLES=(
        "annotation_dataset_items"
        "annotation_datasets"
        "annotation_consensus"
        "annotation_group_items"
        "annotations"
        "annotation_groups"
        "annotation_types"
    )
fi

echo "Checking existing tables..."
echo ""

# Check which tables exist and show their row counts
existing_tables=()
total_rows=0

for table in "${TABLES[@]}"; do
    if check_table "$table"; then
        existing_tables+=("$table")
        # Get row count for total
        count_query="SELECT count() FROM ${ANNOTATION_CLICKHOUSE_DB}.${table}"
        if [ -n "$ANNOTATION_CLICKHOUSE_PASS" ]; then
            count=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}&password=${ANNOTATION_CLICKHOUSE_PASS}" --data-binary "$count_query")
        else
            count=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}" --data-binary "$count_query")
        fi
        total_rows=$((total_rows + count))
    fi
done

echo ""
echo "Summary:"
echo "  Tables found: ${#existing_tables[@]}"
echo "  Total rows to delete: $total_rows"
echo ""

if [ ${#existing_tables[@]} -eq 0 ]; then
    echo -e "${YELLOW}No annotation tables found. Nothing to clear.${NC}"
    exit 0
fi

if [ $total_rows -eq 0 ] && [ "$FORCE_DROP" = false ]; then
    echo -e "${GREEN}All annotation tables are already empty.${NC}"
    exit 0
fi

# Confirm the action
confirm_action

if [ "$FORCE_DROP" = true ]; then
    echo "Dropping annotation tables..."
else
    echo "Clearing annotation tables..."
fi
echo ""

# Clear or drop tables in reverse dependency order
for table in "${TABLES[@]}"; do
    if [[ " ${existing_tables[@]} " =~ " ${table} " ]]; then
        if [ "$FORCE_DROP" = true ]; then
            echo -e "${RED}Dropping table: ${table}${NC}"
            DROP_QUERY="DROP TABLE IF EXISTS ${ANNOTATION_CLICKHOUSE_DB}.${table}"
            result=$(execute_query "$DROP_QUERY" "Dropping $table")
        else
            echo -e "${BLUE}Clearing table: ${table}${NC}"
            # Use TRUNCATE TABLE for better performance
            TRUNCATE_QUERY="TRUNCATE TABLE ${ANNOTATION_CLICKHOUSE_DB}.${table}"
            result=$(execute_query "$TRUNCATE_QUERY" "Truncating $table")
        fi

        if [ -z "$result" ]; then
            if [ "$FORCE_DROP" = true ]; then
                echo -e "  ${GREEN}✓${NC} Table dropped successfully"
            else
                echo -e "  ${GREEN}✓${NC} Table cleared successfully"
            fi
        else
            if [ "$FORCE_DROP" = true ]; then
                echo -e "  ${RED}✗${NC} Error dropping table: $result"
            else
                echo -e "  ${RED}✗${NC} Error clearing table: $result"
            fi
        fi
        echo ""
    fi
done

echo "======================================================"
if [ "$FORCE_DROP" = true ]; then
    echo "Verification - checking if tables were dropped..."
    echo ""

    # Verify all tables are dropped
    all_dropped=true
    for table in "${existing_tables[@]}"; do
        exists_query="SELECT count() FROM system.tables WHERE database = '${ANNOTATION_CLICKHOUSE_DB}' AND name = '${table}'"
        if [ -n "$ANNOTATION_CLICKHOUSE_PASS" ]; then
            exists=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}&password=${ANNOTATION_CLICKHOUSE_PASS}" --data-binary "$exists_query")
        else
            exists=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}" --data-binary "$exists_query")
        fi

        if [ "$exists" -eq 0 ]; then
            echo -e "${GREEN}✓${NC} ${table}: dropped successfully"
        else
            echo -e "${RED}✗${NC} ${table}: still exists (should be dropped)"
            all_dropped=false
        fi
    done

    echo ""
    if [ "$all_dropped" = true ]; then
        echo -e "${GREEN}🎉 All annotation tables dropped successfully!${NC}"
        echo ""
        echo "The annotation tables have been completely removed."
        echo "To recreate the tables, run:"
        echo "  ./scripts/create_annotation_tables.sh"
        echo ""
        echo "To recreate and populate with sample data, run:"
        echo "  ./scripts/create_annotation_tables.sh"
        echo "  python3 ./scripts/populate_annotation_sample_data.py"
    else
        echo -e "${RED}⚠ Some tables may not have been dropped completely.${NC}"
        echo "Please check the errors above and try again if needed."
    fi
else
    echo "Verification - checking table row counts..."
    echo ""

    # Verify all tables are empty
    all_clear=true
    for table in "${existing_tables[@]}"; do
        count_query="SELECT count() FROM ${ANNOTATION_CLICKHOUSE_DB}.${table}"
        if [ -n "$ANNOTATION_CLICKHOUSE_PASS" ]; then
            count=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}&password=${ANNOTATION_CLICKHOUSE_PASS}" --data-binary "$count_query")
        else
            count=$(curl -s "${ANNOTATION_CLICKHOUSE_URL}:${ANNOTATION_CLICKHOUSE_PORT_HTTP}/?user=${ANNOTATION_CLICKHOUSE_USER}" --data-binary "$count_query")
        fi

        if [ "$count" -eq 0 ]; then
            echo -e "${GREEN}✓${NC} ${table}: $count rows"
        else
            echo -e "${RED}✗${NC} ${table}: $count rows (should be 0)"
            all_clear=false
        fi
    done

    echo ""
    if [ "$all_clear" = true ]; then
        echo -e "${GREEN}🎉 All annotation tables cleared successfully!${NC}"
        echo ""
        echo "The annotation database is now empty and ready for:"
        echo "  • Fresh test data"
        echo "  • New annotation workflows"
        echo "  • Sample data population"
        echo ""
        echo "To populate with sample data, run:"
        echo "  ./scripts/populate_annotation_sample_data.sh"
    else
        echo -e "${RED}⚠ Some tables may not have been cleared completely.${NC}"
        echo "Please check the errors above and try again if needed."
    fi
fi

echo "======================================================"
