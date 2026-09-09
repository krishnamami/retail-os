#!/bin/bash
# Build Lambda deployment package with psycopg2 in correct environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
OUTPUT_DIR="$PROJECT_ROOT/dist"

echo "[1] Cleaning previous build..."
rm -rf "$BUILD_DIR" "$OUTPUT_DIR"
mkdir -p "$BUILD_DIR" "$OUTPUT_DIR"

echo "[2] Building psycopg2 in Lambda environment..."
cd "$SCRIPT_DIR"

docker build -t claris-lambda-builder:latest . -f Dockerfile
docker run --rm -v "$BUILD_DIR:/build_output" claris-lambda-builder:latest cp -r /tmp/output/python /build_output/

echo "[3] Creating Lambda deployment package..."
cd "$BUILD_DIR"
cp "$SCRIPT_DIR/lambda_function_improved.py" python/lib/python3.9/site-packages/lambda_function.py
cd "$BUILD_DIR/python"
zip -r "$OUTPUT_DIR/lambda_deployment.zip" .

echo "[4] Verifying psycopg2..."
python3 -c "import sys; sys.path.insert(0, '$BUILD_DIR/python/lib/python3.9/site-packages'); import psycopg2; print(f'SUCCESS: psycopg2 {psycopg2.__version__} packaged')"

echo "[5] Package details..."
ls -lh "$OUTPUT_DIR/lambda_deployment.zip"

echo "SUCCESS: Lambda deployment package created at $OUTPUT_DIR/lambda_deployment.zip"
