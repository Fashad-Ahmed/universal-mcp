#!/bin/bash
# Creates demo.db used by demo_record.sh. Not committed to git.
set -e
cd "$(dirname "$0")/.."

sqlite3 demo.db <<'EOF'
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, country TEXT);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, created_at TEXT);
INSERT INTO customers VALUES (1,'Alice','US'),(2,'Bob','UK'),(3,'Carol','US');
INSERT INTO orders VALUES
  (1,1,120.50,'2026-05-01'),(2,1,80.00,'2026-05-15'),
  (3,2,200.00,'2026-05-20'),(4,3,50.00,'2026-05-22'),
  (5,1,30.00,'2026-06-01'),(6,3,75.00,'2026-06-02');
EOF
echo "demo.db created"
