"""
Standalone Software Vendor License Issuance Tool (OFFLINE ONLY)
Used by Cresconic Technologies to mint cryptographically signed Ed25519 commercial license tokens.
This tool is used strictly offline by the vendor and is NOT part of the client web runtime.
"""

import sys
import os
import json
import base64
import argparse
from typing import Optional
from datetime import datetime, timezone, timedelta

from cryptography.hazmat.primitives.asymmetric import ed25519

# Software Vendor Private Key configuration (OFFLINE AIR-GAPPED ONLY - NEVER HARDCODE)
# Private signing keys must be supplied via secure environment variable or --key-file.
PRODUCT_CODE = "SHAHU_MANDI_ERP"

def get_vendor_private_key(explicit_hex: Optional[str] = None) -> ed25519.Ed25519PrivateKey:
    key_hex = explicit_hex or os.environ.get("VENDOR_ED25519_PRIVATE_KEY")
    if not key_hex:
        raise ValueError(
            "Vendor private signing key required. Provide via VENDOR_ED25519_PRIVATE_KEY env var, "
            "--key-file, or programmatic parameter."
        )
    return ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(key_hex.strip()))

def issue_license(
    licensee_name: str,
    license_id: str,
    tier: str = "PRO",
    max_branches: int = 3,
    valid_days: int = 365,
    features: list = None,
    private_key_hex: Optional[str] = None
) -> str:
    if features is None:
        features = ["MULTI_BRANCH", "RTGS_DESK", "OUTWARD_CHALLAN", "AUDIT_LOGS"]

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=valid_days)

    payload = {
        "license_id": license_id,
        "licensee_name": licensee_name,
        "product": PRODUCT_CODE,
        "tier": tier.upper(),
        "max_branches": int(max_branches),
        "issued_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "valid_from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "features": features
    }

    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    priv = get_vendor_private_key(private_key_hex)
    sig = priv.sign(payload_bytes)

    token = (
        base64.urlsafe_b64encode(payload_bytes).decode("utf-8") +
        "." +
        base64.urlsafe_b64encode(sig).decode("utf-8")
    )
    return token

def generate_signed_license_token(
    licensee_name: str = "Rajeshri Shahu Trading Co.",
    tier: str = "PRO",
    max_branches: int = 3,
    valid_days: int = 365,
    license_id: str = "LIC-TEST-2026",
    private_key_hex: Optional[str] = None
) -> str:
    return issue_license(
        licensee_name=licensee_name,
        license_id=license_id,
        tier=tier,
        max_branches=max_branches,
        valid_days=valid_days,
        private_key_hex=private_key_hex
    )

def inspect_license(token: str):
    from licensing import verify_license_token
    valid, msg, payload = verify_license_token(token)
    print("=" * 60)
    print("COMMERCIAL LICENSE TOKEN INSPECTION")
    print("=" * 60)
    print(f"Cryptographic Signature Valid: {valid}")
    print(f"Status / Message: {msg}")
    if payload:
        print("\nDecoded License Claims:")
        for k, v in payload.items():
            print(f"  {k:<20}: {v}")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mandi ERP Commercial License Issuer")
    parser.add_argument("--name", default="Rajeshri Shahu Trading Co.", help="Licensee Name")
    parser.add_argument("--id", default="LIC-RST-2026-MH3B", help="License Identifier")
    parser.add_argument("--tier", default="PRO", help="License Tier (BASIC, PRO, ENTERPRISE)")
    parser.add_argument("--branches", type=int, default=3, help="Max Allowed Operating Branches")
    parser.add_argument("--days", type=int, default=365, help="Validity Days from Now")
    parser.add_argument("--key-hex", help="Vendor Ed25519 Private Key in hex format")
    parser.add_argument("--key-file", help="Path to secure file containing vendor private key hex")
    parser.add_argument("--inspect", help="Inspect an existing license token")

    args = parser.parse_args()

    if args.inspect:
        inspect_license(args.inspect)
    else:
        priv_hex = args.key_hex
        if not priv_hex and args.key_file and os.path.exists(args.key_file):
            with open(args.key_file, "r", encoding="utf-8") as f:
                priv_hex = f.read().strip()
        
        try:
            tok = issue_license(args.name, args.id, args.tier, args.branches, args.days, private_key_hex=priv_hex)
            print("\nGenerated Commercial License Token:")
            print("-" * 60)
            print(tok)
            print("-" * 60)
            inspect_license(tok)
        except Exception as e:
            print(f"Error issuing license: {e}", file=sys.stderr)
            sys.exit(1)
