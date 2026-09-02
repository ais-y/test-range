#!/usr/bin/env python3
"""Recall/precision report for the AIS-Y test range.

Reads groundtruth/manifest.json (the known-answer set) and queries the Aisy
product for the range organisation's findings, then prints recall, precision,
and a by-name list of every miss (expected-but-absent) and extra
(present-but-not-expected).

Besides template-id recall/precision, this also breaks discovery recall down
by discovery_channel (ct / brute_force): did the host/asset show up in the
product at all, independent of whether its templates fired. A separate
control check FAILS if any discovery_channel: none host (the unguessable
control labels - see catalogue.yaml) was discovered; that's a leak or an
over-broad brute-force wordlist, not a scenario to detect.

Two read backends are supported:

  --backend graphql   Hasura GraphQL at https://api-dev.shadw.stream/v1/graphql
                      Auth: bearer token in AISY_TOKEN (or --token).
  --backend mcp       Documents the aisy MCP shape (search_findings/list_assets).
                      Not callable from this standalone script - it prints the
                      exact tool calls an MCP-capable caller should make.

The range organisation id is a parameter. It does not exist until the range org
has been created in the product, so it is intentionally unset here.

Env vars / params:
  AISY_ORG_ID   the range organisation id      (--org-id)      # TODO below
  AISY_TOKEN    bearer token for the endpoint  (--token)
  AISY_GRAPHQL  endpoint override              (--endpoint)

No secrets are embedded in this file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_MANIFEST = HERE.parent / "groundtruth" / "manifest.json"
DEFAULT_ENDPOINT = "https://api-dev.shadw.stream/v1/graphql"

# TODO(range-org): the range organisation id is assigned when the org is
# created in the product. Fill it in here, or pass --org-id / set AISY_ORG_ID.
# There is deliberately no default - a wrong org id would silently score 0%.
RANGE_ORG_ID: str | None = None


# Findings carry the tripped nuclei template id in a scanner-metadata field.
# Adjust the projection if the product exposes it under a different column.
FINDINGS_QUERY = """
query RangeFindings($org: uuid!) {
  findings(where: {organisation_id: {_eq: $org}}) {
    id
    title
    template_id
    metadata
  }
}
"""

# Asset hostnames, for discovery recall (was the host found at all) separate
# from template recall (did a template fire on it). Adjust the projection if
# the product exposes the hostname under a different column/table.
ASSETS_QUERY = """
query RangeAssets($org: uuid!) {
  assets(where: {organisation_id: {_eq: $org}}) {
    id
    hostname
  }
}
"""


def load_manifest(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"manifest not found: {path} (run groundtruth/generate.py first)")
    return json.loads(path.read_text())


def _template_id_of(finding: dict) -> str | None:
    tid = finding.get("template_id")
    if tid:
        return tid
    meta = finding.get("metadata") or {}
    if isinstance(meta, dict):
        return meta.get("template_id") or meta.get("template-id")
    return None


def fetch_findings_graphql(endpoint: str, token: str, org_id: str) -> list[dict]:
    body = json.dumps(
        {"query": FINDINGS_QUERY, "variables": {"org": org_id}}
    ).encode()
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted endpoint)
        payload = json.loads(resp.read())
    if payload.get("errors"):
        sys.exit(f"graphql errors: {json.dumps(payload['errors'], indent=2)}")
    return payload.get("data", {}).get("findings", [])


def fetch_assets_graphql(endpoint: str, token: str, org_id: str) -> list[dict]:
    body = json.dumps({"query": ASSETS_QUERY, "variables": {"org": org_id}}).encode()
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted endpoint)
        payload = json.loads(resp.read())
    if payload.get("errors"):
        sys.exit(f"graphql errors: {json.dumps(payload['errors'], indent=2)}")
    return payload.get("data", {}).get("assets", [])


def print_mcp_instructions(org_id: str | None) -> None:
    print("MCP backend: call the aisy MCP tools as your signed-in user.\n")
    print("  1. search_findings(organisation_id=<org>, limit=1000)")
    print("     -> collect each finding's template id (template_id / metadata)")
    print("  2. list_assets(organisation_id=<org>)")
    print("     -> collect every discovered hostname, for discovery recall")
    print(f"\n  organisation_id = {org_id or '<TODO: range org id>'}")
    print("\nThen score the results against manifest.json the same way")
    print("--backend graphql does (see score() in this file):")
    print("  - template ids -> overall recall/precision")
    print("  - hostnames vs. each scenario's discovery_channel (ct / brute_force)")
    print("    -> per-channel discovery recall")
    print("  - any discovered hostname with discovery_channel: none and")
    print("    tier: control -> CONTROL CHECK FAILURE (leak / over-broad wordlist)")


def score(
    manifest: dict, found_template_ids: set[str], found_hostnames: set[str] | None = None
) -> dict:
    expected = set(manifest.get("expected_templates", []))
    hits = expected & found_template_ids
    misses = expected - found_template_ids
    extras = found_template_ids - expected

    recall = len(hits) / len(expected) if expected else 0.0
    precision = len(hits) / len(found_template_ids) if found_template_ids else 0.0

    # Per-scenario miss detail so a gap names the app, not just a template id.
    scenario_misses = [
        {
            "id": s["id"],
            "hostname": s["hostname"],
            "missing": [t for t in s["expected_templates"] if t in misses],
        }
        for s in manifest.get("scenarios", [])
        if any(t in misses for t in s["expected_templates"])
    ]

    # Discovery recall per channel: was the host/asset found at all, distinct
    # from whether its templates fired. Only ct/brute_force scenarios count -
    # discovery_channel: none scenarios that aren't controls (e.g. the legacy
    # raw-service host) are out of scope for both this and the control check.
    found_hostnames = found_hostnames or set()
    by_channel: dict[str, dict] = {}
    for s in manifest.get("scenarios", []):
        channel = s.get("discovery_channel")
        if channel not in ("ct", "brute_force"):
            continue
        stats = by_channel.setdefault(channel, {"total": 0, "found": [], "missed": []})
        stats["total"] += 1
        bucket = "found" if s["hostname"] in found_hostnames else "missed"
        stats[bucket].append(s["id"])
    for stats in by_channel.values():
        stats["recall"] = len(stats["found"]) / stats["total"] if stats["total"] else 0.0

    # Control check: any tier: control scenario (the unguessable
    # discovery_channel: none hosts) that got discovered is a real signal.
    control_hits = [
        s["id"]
        for s in manifest.get("scenarios", [])
        if s.get("tier") == "control" and s["hostname"] in found_hostnames
    ]

    return {
        "recall": recall,
        "precision": precision,
        "expected": sorted(expected),
        "hits": sorted(hits),
        "misses": sorted(misses),
        "extras": sorted(extras),
        "scenario_misses": scenario_misses,
        "discovery_by_channel": by_channel,
        "control_hits": sorted(control_hits),
    }


def print_report(result: dict) -> None:
    print("=" * 60)
    print("AIS-Y test range - recall report")
    print("=" * 60)
    print(f"recall:    {result['recall']:.1%}  "
          f"({len(result['hits'])}/{len(result['expected'])} template ids)")
    print(f"precision: {result['precision']:.1%}")

    print("\nDISCOVERY RECALL BY CHANNEL (asset found, regardless of template):")
    for channel in ("ct", "brute_force"):
        stats = result["discovery_by_channel"].get(channel)
        if not stats:
            print(f"  {channel:<12} no scenarios")
            continue
        print(
            f"  {channel:<12} {stats['recall']:.1%}  "
            f"({len(stats['found'])}/{stats['total']})"
        )
        if stats["missed"]:
            print(f"      missed: {', '.join(stats['missed'])}")

    if result["control_hits"]:
        print("\nCONTROL CHECK: FAILED - control host(s) discovered:")
        for cid in result["control_hits"]:
            print(f"  - {cid}")
    else:
        print("\nCONTROL CHECK: passed - no control host discovered.")

    if result["scenario_misses"]:
        print("\nMISSES (expected but not found):")
        for m in result["scenario_misses"]:
            print(f"  - {m['id']:<24} {m['hostname']}")
            print(f"      missing: {', '.join(m['missing'])}")
    else:
        print("\nMISSES: none - full recall.")

    if result["extras"]:
        print("\nEXTRAS (found but not in catalogue):")
        for t in result["extras"]:
            print(f"  - {t}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--backend", choices=["graphql", "mcp"], default="graphql")
    ap.add_argument("--endpoint", default=os.environ.get("AISY_GRAPHQL", DEFAULT_ENDPOINT))
    ap.add_argument("--org-id", default=os.environ.get("AISY_ORG_ID") or RANGE_ORG_ID)
    ap.add_argument("--token", default=os.environ.get("AISY_TOKEN"))
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)

    if args.backend == "mcp":
        print_mcp_instructions(args.org_id)
        return

    if not args.org_id:
        sys.exit(
            "no org id: set AISY_ORG_ID / --org-id (see RANGE_ORG_ID TODO in this file)"
        )
    if not args.token:
        sys.exit("no token: set AISY_TOKEN / --token")

    findings = fetch_findings_graphql(args.endpoint, args.token, args.org_id)
    found = {tid for f in findings if (tid := _template_id_of(f))}
    assets = fetch_assets_graphql(args.endpoint, args.token, args.org_id)
    found_hostnames = {a["hostname"] for a in assets if a.get("hostname")}
    result = score(manifest, found, found_hostnames)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)

    # Non-zero exit on any template miss or control-host discovery so CI can
    # gate on full recall and a clean control check.
    sys.exit(1 if (result["misses"] or result["control_hits"]) else 0)


if __name__ == "__main__":
    main()
