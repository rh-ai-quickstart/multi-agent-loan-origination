#!/usr/bin/env python3
"""Create requested S3 buckets after the object store accepts authenticated calls."""

import os
import sys
import time

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


def main(arguments: list[str] | None = None) -> None:
    required = ("S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_REGION")
    missing = [name for name in required if not os.environ.get(name)]
    buckets = arguments if arguments is not None else sys.argv[1:]
    if missing or not buckets:
        detail = f"missing required environment variables: {', '.join(missing)}" if missing else "no buckets given"
        raise SystemExit(detail)

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.environ["S3_REGION"],
        config=Config(
            connect_timeout=5,
            read_timeout=5,
            retries={"total_max_attempts": 1, "mode": "standard"},
            s3={"addressing_style": "path"},
        ),
    )

    existing = None
    for attempt in range(1, 31):
        try:
            existing = {item["Name"] for item in client.list_buckets().get("Buckets", [])}
            break
        except (BotoCoreError, ClientError) as error:
            print(f"S3 authentication attempt {attempt}/30 failed: {error}", flush=True)
            if attempt < 30:
                time.sleep(2)

    if existing is None:
        raise SystemExit("S3 endpoint did not accept authenticated requests after 30 attempts")

    for bucket in buckets:
        if bucket in existing:
            print(f"Bucket already exists: {bucket}", flush=True)
            continue
        try:
            client.create_bucket(Bucket=bucket)
            print(f"Created bucket: {bucket}", flush=True)
        except ClientError:
            # A concurrent bootstrap may have created it after our initial list.
            if bucket in {item["Name"] for item in client.list_buckets().get("Buckets", [])}:
                print(f"Bucket already exists: {bucket}", flush=True)
                continue
            raise


if __name__ == "__main__":
    main()
