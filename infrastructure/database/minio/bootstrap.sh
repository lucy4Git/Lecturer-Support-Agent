#!/bin/sh
set -eu

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing "local/$OBJECT_STORAGE_BUCKET"
mc version enable "local/$OBJECT_STORAGE_BUCKET"
mc anonymous set none "local/$OBJECT_STORAGE_BUCKET"
echo "MinIO bucket created with versioning enabled and anonymous access disabled."
