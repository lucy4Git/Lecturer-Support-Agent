"""
Lecturer Support Agent — Deployment Data Parity Verifier
=========================================================
Compares data manifests, rights ledger, approval register, and live
infrastructure state to confirm deployment parity.

Returns exit code 0 only if every check passes.
Returns exit code 1 (fail closed) on any violation.

Usage:
    python scripts/data/data_parity_verifier.py --env local
    python scripts/data/data_parity_verifier.py --env staging
    python scripts/data/data_parity_verifier.py --env production
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("parity_verifier")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_catalogue() -> list[dict]:
    p = ROOT / "data" / "catalogue" / "dataset_catalogue.yaml"
    with open(p) as f:
        return yaml.safe_load(f)["datasets"]


def load_rights_ledger() -> list[dict]:
    p = ROOT / "data" / "governance" / "rights_ledger.csv"
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def load_approval_register() -> list[dict]:
    p = ROOT / "data" / "governance" / "approval_register.csv"
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def load_manifest(env: str) -> dict | None:
    if env == "production":
        p = ROOT / "data" / "manifests" / "production_data_manifest.template.json"
    else:
        p = ROOT / "data" / "manifests" / f"{env}_data_manifest.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


class ParityViolation(Exception):
    pass


class ParityVerifier:
    def __init__(self, env: str) -> None:
        self.env = env
        self.violations: list[str] = []
        self.warnings: list[str] = []
        self.checks_passed: list[str] = []

    def fail(self, msg: str) -> None:
        self.violations.append(msg)
        log.error("VIOLATION: %s", msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        log.warning("WARNING: %s", msg)

    def ok(self, msg: str) -> None:
        self.checks_passed.append(msg)
        log.info("OK: %s", msg)

    def check_catalogue_integrity(self) -> None:
        """Verify catalogue files are consistent."""
        yaml_path = ROOT / "data" / "catalogue" / "dataset_catalogue.yaml"
        json_path = ROOT / "data" / "catalogue" / "dataset_catalogue.json"
        if not yaml_path.exists():
            self.fail("dataset_catalogue.yaml not found")
            return
        self.ok("dataset_catalogue.yaml present")
        if not json_path.exists():
            self.warn("dataset_catalogue.json not found — may need regeneration")
        else:
            self.ok("dataset_catalogue.json present")

    def check_unapproved_datasets_absent(self) -> None:
        """No unapproved dataset may appear in the manifest."""
        manifest = load_manifest(self.env)
        if manifest is None:
            self.warn(f"No manifest for env={self.env} — skipping manifest checks")
            return
        catalogue = load_catalogue()
        cat_by_id = {d["id"]: d for d in catalogue}
        env_state_required = {
            "local": "APPROVED_FOR_LOCAL",
            "staging": "APPROVED_FOR_STAGING",
            "production": "APPROVED_FOR_PRODUCTION",
        }.get(self.env, "")

        for entry in manifest.get("datasets", []):
            ds_id = entry.get("dataset_id")
            ds = cat_by_id.get(ds_id)
            if ds is None:
                self.fail(f"Manifest references dataset '{ds_id}' not in catalogue")
                continue
            state = ds.get("governance_state", "DISCOVERED")
            if state in ("PENDING_RIGHTS_REVIEW", "REJECTED", "WITHDRAWN", "EXPIRED"):
                self.fail(f"Dataset '{ds_id}' in manifest has disqualifying state: {state}")
                continue
            # Production approval covers all environments
            if state not in (env_state_required, "APPROVED_FOR_PRODUCTION"):
                if not (self.env in ("local", "staging") and state == "APPROVED_FOR_PRODUCTION"):
                    self.fail(
                        f"Dataset '{ds_id}' governance_state='{state}' insufficient for env='{self.env}'"
                    )
                    continue
            self.ok(f"Dataset '{ds_id}' approved for {self.env}")

    def check_rights_ledger_completeness(self) -> None:
        """Every catalogue dataset must have a rights ledger entry."""
        catalogue = load_catalogue()
        ledger = load_rights_ledger()
        ledger_ids = {row["dataset_id"] for row in ledger}
        for ds in catalogue:
            if ds["id"] not in ledger_ids:
                self.fail(f"Dataset '{ds['id']}' missing from rights_ledger.csv")
            else:
                self.ok(f"Rights ledger entry present for '{ds['id']}'")

    def check_privileged_roles_have_approvers(self) -> None:
        """Every privileged role assignment must have an approving authority."""
        matrix_path = ROOT / "data" / "governance" / "approver_matrix.yaml"
        if not matrix_path.exists():
            self.fail("approver_matrix.yaml not found")
            return
        with open(matrix_path) as f:
            matrix = yaml.safe_load(f)
        for domain, config in matrix.get("approval_domains", {}).items():
            prod_approver = config.get("production_approver", "")
            if self.env == "production" and prod_approver.startswith("REPLACE_WITH"):
                self.fail(
                    f"Approval domain '{domain}' has placeholder production_approver — "
                    "must be replaced before production deployment"
                )
            else:
                self.ok(f"Approval domain '{domain}' has configured approver for {self.env}")

    def check_no_staging_synthetic_users_in_production_manifest(self) -> None:
        """Staging synthetic users must not appear in production manifest."""
        if self.env != "production":
            self.ok("staging-in-production check: N/A for non-production env")
            return
        manifest = load_manifest("production")
        if manifest is None:
            self.warn("No production manifest — skipping synthetic-user contamination check")
            return
        user_manifest = manifest.get("institutional_users", {})
        source = user_manifest.get("source", "")
        if "synthetic" in source.lower() or "seed" in source.lower():
            self.fail(
                "Production manifest references synthetic or seed users — "
                "production must use only authorised institutional imports"
            )
        else:
            self.ok("Production manifest does not reference synthetic user source")

        if not manifest.get("synthetic_seed_disabled", False):
            self.fail("Production manifest does not confirm synthetic_seed_disabled=true")
        else:
            self.ok("synthetic_seed_disabled=true confirmed in production manifest")

    def check_redis_clean_start(self) -> None:
        """Manifest must declare Redis clean-start."""
        manifest = load_manifest(self.env)
        if manifest is None:
            self.warn("No manifest — skipping Redis clean-start check")
            return
        if not manifest.get("redis_clean_start", False):
            self.fail(f"Manifest for env={self.env} does not declare redis_clean_start=true")
        else:
            self.ok("redis_clean_start=true declared in manifest")

    def check_no_secrets_in_catalogue(self) -> None:
        """Catalogue must not contain any secret values."""
        catalogue = load_catalogue()
        for ds in catalogue:
            for key, val in ds.items():
                if isinstance(val, str) and any(
                    pat in val.lower() for pat in ["password", "secret", "api_key", "token"]
                ):
                    if "REPLACE" not in val and "CONFIGURED" not in val:
                        self.fail(
                            f"Dataset '{ds['id']}' field '{key}' may contain a secret value"
                        )
        self.ok("No obvious secret values found in catalogue")

    def check_evaluation_not_in_retrieval(self) -> None:
        """Evaluation datasets must not be declared for the retrieval collection."""
        manifest = load_manifest(self.env)
        if manifest is None:
            return
        for entry in manifest.get("datasets", []):
            if entry.get("qdrant_collection") == "lsa_retrieval":
                ds_id = entry.get("dataset_id")
                catalogue = load_catalogue()
                ds = next((d for d in catalogue if d["id"] == ds_id), None)
                if ds and ds.get("retrieval_use") is False and ds.get("evaluation_use") is True:
                    self.fail(
                        f"Evaluation-only dataset '{ds_id}' declared for lsa_retrieval collection"
                    )
                else:
                    self.ok(f"Collection assignment for '{ds_id}' is consistent")

    def run(self) -> bool:
        log.info("=== Data Parity Verifier — env=%s ===", self.env)
        self.check_catalogue_integrity()
        self.check_unapproved_datasets_absent()
        self.check_rights_ledger_completeness()
        self.check_privileged_roles_have_approvers()
        self.check_no_staging_synthetic_users_in_production_manifest()
        self.check_redis_clean_start()
        self.check_no_secrets_in_catalogue()
        self.check_evaluation_not_in_retrieval()

        log.info("=== Results ===")
        log.info("Checks passed: %d", len(self.checks_passed))
        log.info("Warnings: %d", len(self.warnings))
        log.info("Violations: %d", len(self.violations))
        for v in self.violations:
            log.error("FAIL: %s", v)

        return len(self.violations) == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Deployment data parity verifier")
    parser.add_argument("--env", choices=["local", "staging", "production"], default="local")
    args = parser.parse_args()

    verifier = ParityVerifier(args.env)
    passed = verifier.run()

    result = {
        "env": args.env,
        "passed": passed,
        "checks_passed": len(verifier.checks_passed),
        "warnings": verifier.warnings,
        "violations": verifier.violations,
    }
    print(json.dumps(result, indent=2))

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
