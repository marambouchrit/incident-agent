#!/usr/bin/env bash
# Unrelated documentation commit, not deployed.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

cat >> README.md <<'EOF'

## API examples
```
curl "localhost:18000/products?category=books&page=1"
curl "localhost:18000/products/search?q=lamp"
curl "localhost:18000/orders?user_id=42"
curl -X POST localhost:18000/checkout -H 'content-type: application/json' \
     -d '{"user_id": 42, "items": [{"product_id": 7, "quantity": 1}]}'
```
EOF

commit_as "$LINA" "Add API usage examples to README"
