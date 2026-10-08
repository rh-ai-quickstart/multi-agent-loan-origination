"""Render the chart to verify release tags reach every application container."""

from pathlib import Path
import subprocess
import unittest

import yaml


CHART = Path(__file__).parents[1]
REGISTRY = "quay.io/rh-ai-quickstart"


class ImageTagTests(unittest.TestCase):
    def assert_rendered_tags(
        self,
        overrides: dict[str, str],
        *,
        api: str,
        ui: str,
        mcp: str,
    ) -> None:
        command = [
            "helm",
            "template",
            "mortgage-ai",
            str(CHART),
            "--set",
            "seed.enabled=true",
        ]
        for key, value in overrides.items():
            command.extend(["--set-string", f"{key}={value}"])
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=30
        )
        containers = {}
        for document in yaml.safe_load_all(result.stdout):
            if not document or document.get("kind") not in {"Deployment", "Job"}:
                continue
            pod = document["spec"]["template"]["spec"]
            for container in pod.get("initContainers", []) + pod.get("containers", []):
                key = (document["metadata"]["name"], container["name"])
                containers[key] = container["image"]

        expected = {
            ("mortgage-ai-api", "api"): f"mortgage-ai-api:{api}",
            ("mortgage-ai-api", "run-migrations"): f"mortgage-ai-api:{api}",
            ("mortgage-ai-seed", "seed"): f"mortgage-ai-api:{api}",
            (
                "mortgage-ai-s4-create-buckets-1",
                "create-buckets",
            ): f"mortgage-ai-api:{api}",
            ("mortgage-ai-ui", "ui"): f"mortgage-ai-ui:{ui}",
            ("mcp-risk-server", "mcp-risk-server"): f"mortgage-ai-api:{mcp}",
        }
        for key, image in expected.items():
            with self.subTest(container=key):
                self.assertIn(key, containers)
                self.assertEqual(containers[key], f"{REGISTRY}/{image}")

    def test_default_release_is_latest(self) -> None:
        self.assert_rendered_tags({}, api="latest", ui="latest", mcp="latest")

    def test_global_tag_selects_every_application_container(self) -> None:
        self.assert_rendered_tags(
            {"global.imageTag": "release-test"},
            api="release-test",
            ui="release-test",
            mcp="release-test",
        )

    def test_api_override_also_selects_migration_seed_and_bootstrap(self) -> None:
        self.assert_rendered_tags(
            {"global.imageTag": "release-test", "api.image.tag": "api-test"},
            api="api-test",
            ui="release-test",
            mcp="release-test",
        )

    def test_ui_override_preserves_other_component_tags(self) -> None:
        self.assert_rendered_tags(
            {"global.imageTag": "release-test", "ui.image.tag": "ui-test"},
            api="release-test",
            ui="ui-test",
            mcp="release-test",
        )

    def test_mcp_override_preserves_other_component_tags(self) -> None:
        self.assert_rendered_tags(
            {"global.imageTag": "release-test", "mcpRiskServer.image.tag": "mcp-test"},
            api="release-test",
            ui="release-test",
            mcp="mcp-test",
        )


if __name__ == "__main__":
    unittest.main()
