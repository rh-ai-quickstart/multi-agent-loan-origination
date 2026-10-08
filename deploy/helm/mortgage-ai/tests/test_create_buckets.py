"""Focused behavior checks for the bundled S4 bucket bootstrap script."""

import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError


SCRIPT = Path(__file__).parents[1] / "files" / "create-buckets.py"
SPEC = importlib.util.spec_from_file_location("create_buckets", SCRIPT)
assert SPEC and SPEC.loader
create_buckets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(create_buckets)

S3_ENV = {
    "S3_ENDPOINT": "http://s4:7480",
    "S3_ACCESS_KEY": "s4admin",
    "S3_SECRET_KEY": "s4secret",
    "S3_REGION": "us-east-1",
}


class CreateBucketsTests(unittest.TestCase):
    def test_skips_buckets_that_already_exist(self) -> None:
        client = Mock()
        client.list_buckets.return_value = {
            "Buckets": [{"Name": "documents"}, {"Name": "mlflow"}],
        }

        with patch.dict(os.environ, S3_ENV, clear=True), patch.object(
            create_buckets.boto3, "client", return_value=client
        ):
            create_buckets.main(["documents", "mlflow"])

        client.create_bucket.assert_not_called()

    def test_retries_authentication_then_creates_missing_buckets(self) -> None:
        client = Mock()
        client.list_buckets.side_effect = [
            ClientError({"Error": {"Code": "AccessDenied", "Message": "not ready"}}, "ListBuckets"),
            {"Buckets": []},
        ]

        with patch.dict(os.environ, S3_ENV, clear=True), patch.object(
            create_buckets.boto3, "client", return_value=client
        ), patch.object(create_buckets.time, "sleep") as sleep:
            create_buckets.main(["documents", "mlflow"])

        sleep.assert_called_once_with(2)
        self.assertEqual(
            client.create_bucket.call_args_list,
            [
                unittest.mock.call(Bucket="documents"),
                unittest.mock.call(Bucket="mlflow"),
            ],
        )

    def test_rejects_missing_connection_settings(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(
            SystemExit, "S3_ENDPOINT"
        ):
            create_buckets.main(["documents"])


if __name__ == "__main__":
    unittest.main()
