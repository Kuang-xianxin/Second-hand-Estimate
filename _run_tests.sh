#!/bin/bash
# Find Python and run tests
cd "D:/my progect/估二手/backend" || exit 1

# Try to find Python
for py in python3 python py; do
    if command -v $py &>/dev/null; then
        echo "Found: $py at $(which $py)"
        $py --version 2>&1
        echo "=== Running keyword_tier tests ==="
        $py -m pytest tests/test_keyword_tier.py -v --tb=short 2>&1
        echo "=== Running crawl_worker tests ==="
        $py -m pytest tests/test_crawl_worker.py -v --tb=short 2>&1
        exit $?
    fi
done

echo "ERROR: No Python found on PATH"
echo "PATH=$PATH"
exit 1
