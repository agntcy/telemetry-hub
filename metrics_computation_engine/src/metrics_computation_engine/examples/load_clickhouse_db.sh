#!/bin/bash -eux

CLICKHOUSE_DB_USER="admin"
CLICKHOUSE_DB_PASS="admin"

FILE_LIST=(
"./data/otel_traces.json"
)

if [[ -z $(which clickhouse-client) ]]
then
  echo "You need to have clickhouse-client installed for this script to work."
  echo "Check https://clickhouse.com/docs/interfaces/cli to install it."
  exit 1
fi

for table_file in ${FILE_LIST[@]}
do
  table_name=$(basename ${table_file} | cut -d'.' -f 1)
  cat ${table_file} | clickhouse-client --user ${CLICKHOUSE_DB_USER} --password ${CLICKHOUSE_DB_PASS} -q \
    "INSERT INTO ${table_name} FORMAT JSONEachRow"
  echo "Loaded data into ${table_name}"
done
