#!/usr/bin/env python3
"""Emit manifest.json - the complete known-answer set for the test range.

Merges the authoritative catalogue.yaml with the range's Terraform outputs
(base domain + per-host elastic IPs) and expands the {base_domain} / {eip}
placeholders so downstream tooling has concrete hostnames and addresses.

Usage:
    generate.py --tf-output outputs.json [--catalogue catalogue.yaml] \
                [--out manifest.json]

--tf-output is `terraform output -json` captured from the range stack. Expected
shape (only these keys are read):
    {
      "base_domain": {"value": "range.example.net"},
      "host_eips":   {"value": {"range-web-1": "203.0.113.10", ...}}
    }
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).parent


def _load_tf_outputs(path: Path) -> tuple[str, dict[str, str]]:
    raw = json.loads(path.read_text())

    def _val(key: str, default):
        node = raw.get(key)
        return node.get("value", default) if isinstance(node, dict) else default

    base_domain = _val("base_domain", "range.invalid")
    host_eips = _val("host_eips", {})
    return base_domain, host_eips


def _fill(text: str, base_domain: str) -> str:
    return text.replace("{base_domain}", base_domain)


def build_manifest(catalogue: dict, base_domain: str, host_eips: dict[str, str]) -> dict:
    scenarios = []
    for entry in catalogue.get("scenarios", []):
        host = entry["host"]
        scenarios.append(
            {
                "id": entry["id"],
                "host": host,
                "ip": host_eips.get(host),  # None until Terraform has run
                "hostname": _fill(entry["hostname"], base_domain),
                "ports": entry.get("ports", []),
                "scheme": entry.get("scheme"),
                "app": entry.get("app"),
                "tier": entry.get("tier"),
                "discovery": entry.get("discovery", "none"),
                "expected_templates": entry.get("expected_templates", []),
                "custom_template": entry.get("custom_template", False),
                "certificate_issues": entry.get("certificate_issues", []),
                "planted_secrets": entry.get("planted_secrets", []),
            }
        )

    all_templates = sorted(
        {t for s in scenarios for t in s["expected_templates"]}
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "range": catalogue.get("meta", {}).get("range", "aisy-test-range"),
        "base_domain": base_domain,
        "contact": catalogue.get("meta", {}).get("contact"),
        "counts": {
            "scenarios": len(scenarios),
            "expected_templates": len(all_templates),
            "cert_defect_hosts": sum(1 for s in scenarios if s["certificate_issues"]),
        },
        "expected_templates": all_templates,
        "scenarios": scenarios,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tf-output", type=Path, help="terraform output -json file")
    ap.add_argument("--catalogue", type=Path, default=HERE / "catalogue.yaml")
    ap.add_argument("--out", type=Path, default=HERE / "manifest.json")
    args = ap.parse_args()

    catalogue = yaml.safe_load(args.catalogue.read_text())
    if args.tf_output and args.tf_output.exists():
        base_domain, host_eips = _load_tf_outputs(args.tf_output)
    else:
        # No Terraform yet: keep the logical base domain, leave IPs unresolved.
        base_domain = catalogue.get("meta", {}).get("base_domain", "range.invalid")
        host_eips = {}

    manifest = build_manifest(catalogue, base_domain, host_eips)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"wrote {args.out} "
        f"({manifest['counts']['scenarios']} scenarios, "
        f"{manifest['counts']['expected_templates']} template ids)"
    )


if __name__ == "__main__":
    main()
