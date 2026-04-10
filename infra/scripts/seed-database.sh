#!/bin/bash
# seed-database.sh — Run schema.sql and seed-data.sql against Azure SQL
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
fi

if [ -z "$SQL_CONNECTION_STRING" ]; then
  echo "❌ SQL_CONNECTION_STRING not set. Run output-env.sh first."
  exit 1
fi

# Extract server name from connection string
SERVER_NAME=$(echo "$SQL_CONNECTION_STRING" | grep -oP 'Server=\K[^;]+')
DATABASE_NAME="ops-assistant-db"

echo "  Target: $SERVER_NAME / $DATABASE_NAME"

# Run schema
echo "  Applying schema..."
sqlcmd -S "$SERVER_NAME" -d "$DATABASE_NAME" \
  --authentication-method=ActiveDirectoryDefault \
  -i "$PROJECT_ROOT/database/schema.sql"

# Run seed data
echo "  Inserting seed data..."
sqlcmd -S "$SERVER_NAME" -d "$DATABASE_NAME" \
  --authentication-method=ActiveDirectoryDefault \
  -i "$PROJECT_ROOT/database/seed-data.sql"

echo "  ✅ Database seeded successfully"
