#!/bin/bash
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

# Script to create annotation database and tables in ClickHouse
# This script will:
# 1. Check if the specified database exists, and create it if it doesn't
# 2. Parse the annotation_schema_clickhouse.sql file and create all tables defined in it
# 3. Execute each CREATE TABLE statement individually to handle ClickHouse limitations
# 4. Provide detailed feedback on the creation process
#
# Usage: ./create_annotation_tables.sh [clickhouse_host] [clickhouse_port] [database] [user] [password]
#
# The script will first try to load configuration from .env file, then use
# command line arguments if provided to override the defaults.
# All table definitions are read from annotation_schema_clickhouse.sql

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# check default env files
ENV_FILE=".env"

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

SQL_FILE="$SCRIPT_DIR/annotation_schema_clickhouse.sql"

echo "Creating annotation tables in ClickHouse..."
echo "Host: $ANNOTATION_CLICKHOUSE_URL"
echo "Port: $ANNOTATION_CLICKHOUSE_PORT_HTTP"
echo "Database: $ANNOTATION_CLICKHOUSE_DB"
echo "User: $ANNOTATION_CLICKHOUSE_USER"

# Build the base curl command for authentication
BASE_CURL_CMD="curl -X POST"

if [ ! -z "$ANNOTATION_CLICKHOUSE_PASS" ]; then
    BASE_CURL_CMD="$BASE_CURL_CMD -u $ANNOTATION_CLICKHOUSE_USER:$ANNOTATION_CLICKHOUSE_PASS"
fi

# Check if the database exists, if not create it
echo "Checking if database '$ANNOTATION_CLICKHOUSE_DB' exists..."

# First, check if the database exists
CHECK_DB_CMD="$BASE_CURL_CMD \"http://$ANNOTATION_CLICKHOUSE_URL:$ANNOTATION_CLICKHOUSE_PORT_HTTP/\" -d \"SELECT name FROM system.databases WHERE name = '$ANNOTATION_CLICKHOUSE_DB'\""

DB_EXISTS=$(eval "$CHECK_DB_CMD" 2>/dev/null | grep -q "$ANNOTATION_CLICKHOUSE_DB" && echo "true" || echo "false")

if [ "$DB_EXISTS" = "false" ]; then
    echo "Database '$ANNOTATION_CLICKHOUSE_DB' does not exist. Creating it..."

    # Create the database
    CREATE_DB_CMD="$BASE_CURL_CMD \"http://$ANNOTATION_CLICKHOUSE_URL:$ANNOTATION_CLICKHOUSE_PORT_HTTP/\" -d \"CREATE DATABASE IF NOT EXISTS $ANNOTATION_CLICKHOUSE_DB\""

    eval "$CREATE_DB_CMD"

    if [ $? -eq 0 ]; then
        echo "✅ Database '$ANNOTATION_CLICKHOUSE_DB' created successfully!"
    else
        echo "❌ Failed to create database '$ANNOTATION_CLICKHOUSE_DB'"
        exit 1
    fi
else
    echo "✅ Database '$ANNOTATION_CLICKHOUSE_DB' already exists"
fi

# Tables management - use the database-specific URL
CURL_CMD="$BASE_CURL_CMD \"http://$ANNOTATION_CLICKHOUSE_URL:$ANNOTATION_CLICKHOUSE_PORT_HTTP/?database=$ANNOTATION_CLICKHOUSE_DB\""

# Execute the SQL file - parse and execute statements from the file
if [ -f "$SQL_FILE" ]; then
    echo "Creating annotation tables from SQL file: $SQL_FILE"

    # Parse the SQL file to extract individual CREATE TABLE statements
    # Remove comments, empty lines, and split by CREATE TABLE statements
    temp_sql_dir="/tmp/annotation_sql_$$"
    mkdir -p "$temp_sql_dir"

    # Extract CREATE TABLE statements from the SQL file
    # This awk script splits the file by CREATE TABLE statements
    awk -v temp_dir="$temp_sql_dir" '
    BEGIN {
        statement_num = 0
        current_statement = ""
        in_create_table = 0
    }

    # Skip comment lines and empty lines
    /^--/ || /^[[:space:]]*$/ { next }

    # Start of a CREATE TABLE statement
    /^CREATE TABLE/ {
        if (current_statement != "") {
            # Save previous statement
            statement_num++
            output_file = temp_dir "/statement_" statement_num ".sql"
            print current_statement > output_file
            close(output_file)
        }
        current_statement = $0
        in_create_table = 1
        next
    }

    # Continue collecting lines for the current statement
    {
        if (in_create_table) {
            current_statement = current_statement "\n" $0
            # Check if this line ends the statement (contains semicolon at end)
            if (/;[[:space:]]*$/) {
                in_create_table = 0
            }
        }
    }

    END {
        # Save the last statement
        if (current_statement != "") {
            statement_num++
            output_file = temp_dir "/statement_" statement_num ".sql"
            print current_statement > output_file
            close(output_file)
        }
        count_file = temp_dir "/total_count"
        print statement_num > count_file
        close(count_file)
    }
    ' "$SQL_FILE"

    # Get the total number of statements
    if [ -f "$temp_sql_dir/total_count" ]; then
        total_count=$(cat "$temp_sql_dir/total_count")
    else
        total_count=0
    fi

    if [ $total_count -eq 0 ]; then
        echo "❌ No CREATE TABLE statements found in $SQL_FILE"
        rm -rf "$temp_sql_dir"
        exit 1
    fi

    # Execute each statement
    success_count=0

    for i in $(seq 1 $total_count); do
        statement_file="$temp_sql_dir/statement_$i.sql"

        if [ -f "$statement_file" ]; then
            # Extract table name for better logging
            table_name=$(grep -o "CREATE TABLE[^(]*" "$statement_file" | sed 's/CREATE TABLE IF NOT EXISTS //' | sed 's/CREATE TABLE //' | tr -d ' ')

            echo "Creating table $i/$total_count: $table_name..."

            # Remove semicolon from the end and execute
            sed 's/;[[:space:]]*$//' "$statement_file" | eval "$CURL_CMD --data-binary @-"

            if [ $? -eq 0 ]; then
                success_count=$((success_count + 1))
                echo "✅ Table $table_name created successfully"
            else
                echo "❌ Failed to create table $table_name"
            fi
        fi
    done

    # Clean up temporary files
    rm -rf "$temp_sql_dir"

    if [ $success_count -eq $total_count ]; then
        echo "✅ All $total_count annotation tables created successfully!"
    else
        echo "❌ Failed to create some annotation tables ($success_count/$total_count succeeded)"
        exit 1
    fi
else
    echo "❌ SQL file not found: $SQL_FILE"
    exit 1
fi

echo "Done!"
