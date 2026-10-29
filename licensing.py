"""
Commercial Licensing Module for Rajeshri Shahu Mandi ERP.
Uses Ed25519 asymmetric cryptographic signatures to verify commercial licenses.
The software vendor holds the private signing key offline.
The distributed ERP embeds only the vendor public key.
"""

import base64
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

# Embedded Official Vendor Public Key (Cresconic Technologies)
VENDOR_PUBLIC_KEY_HEX = "1b6daad3bf761546b3c7433dbf823b6a696483868f8425eab6779f28310dfda8"
PRODUCT_CODE = "SHAHU_MANDI_ERP"

# Default signed commercial license token for initial deployment
DEFAULT_COMMERCIAL_LICENSE_TOKEN = (
    "eyJleHBpcmVzX2F0IjoiMjAyNy0wMy0zMVQyMzo1OTo1OVoiLCJmZWF0dXJlcyI6WyJNVUxUSV9CUkFOQ0giLCJSVEdTX0RFU0siLCJPVVRXQVJEX0NIQUxMQU4iLCJBVURJVF9MT0dTIl0sImlzc3VlZF9hdCI6IjIwMjYtMDQtMDFUMDA6MDA6MDBaIiwibGljZW5zZV9pZCI6IkxJQy1SU1QtMjAyNi1NSDNCLTg5QTEyRiIsImxpY2Vuc2VlX25hbWUiOiJSYWplc2hyaSBTaGFodSBUcmFkaW5nIENvLiIsIm1heF9icmFuY2hlcyI6MywicHJvZHVjdCI6IlNIQUhVX01BTkRJX0VSUCIsInRpZXIiOiJQUk8ifQ==."
    "Zd0k1Lz8JRi8C33R0lx_iVX9vZFwSJsr9G1QRx-US0jor8EtUtbjEfEVyihQrgr0cwUvk29Kp50Dsf__4n6HCQ=="
)


def get_public_key() -> ed25519.Ed25519PublicKey:
    return ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(VENDOR_PUBLIC_KEY_HEX))


def verify_license_token(token: str, custom_public_key_hex: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Cryptographically verifies an Ed25519 signed license token string.
    Returns (is_valid, reason_or_message, payload_dict).
    """
    if not token or not isinstance(token, str):
        return False, "License token is empty or missing.", None

    token = token.strip()
    parts = token.split(".")
    if len(parts) != 2:
        return False, "Malformed license token format (expected payload.signature).", None

    payload_b64, sig_b64 = parts

    try:
        # Restore padding if stripped
        payload_b64_padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        sig_b64_padded = sig_b64 + "=" * (-len(sig_b64) % 4)

        payload_bytes = base64.urlsafe_b64decode(payload_b64_padded)
        sig_bytes = base64.urlsafe_b64decode(sig_b64_padded)
    except Exception as e:
        return False, f"Failed to base64-decode license token: {e}", None

    # Verify signature
    try:
        pub_hex = custom_public_key_hex or VENDOR_PUBLIC_KEY_HEX
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        pub_key.verify(sig_bytes, payload_bytes)
    except InvalidSignature:
        return False, "Digital signature verification failed. Token has been tampered with or was signed by an unauthorized issuer.", None
    except Exception as e:
        return False, f"Signature verification error: {e}", None

    # Parse and validate payload
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        return False, f"Invalid JSON payload inside license token: {e}", None

    # 1. Product check
    if payload.get("product") != PRODUCT_CODE:
        return False, f"License is for product '{payload.get('product')}', but this application requires '{PRODUCT_CODE}'.", payload

    # 2. Expiry check
    expires_at_str = payload.get("expires_at")
    if not expires_at_str:
        return False, "License does not contain an expiration date.", payload

    try:
        # Parse ISO date with or without timezone
        if expires_at_str.endswith("Z"):
            expires_at = datetime.fromisoformat(expires_at_str[:-1]).replace(tzinfo=timezone.utc)
        else:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

        now_utc = datetime.now(timezone.utc)
        if now_utc > expires_at:
            return False, f"Commercial license expired on {expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}.", payload
    except Exception as e:
        return False, f"Invalid date format in license expires_at ({expires_at_str}): {e}", payload

    # 3. Branch limit
    if "max_branches" not in payload or int(payload["max_branches"]) <= 0:
        return False, "License has invalid or zero max_branches configuration.", payload

    return True, "License signature and validity verified.", payload


def get_active_license(conn) -> Dict[str, Any]:
    """
    Reads license from SQLite system_settings, validates signature and constraints,
    and returns a normalized license status dictionary.
    """
    cur = conn.cursor()
    cur.execute("SELECT setting_key, setting_value FROM system_settings WHERE scope='SUPER_ADMIN'")
    settings = {r["setting_key"]: r["setting_value"] for r in cur.fetchall()}

    token = settings.get("license_token")

    # If license_token is not yet saved, check if we need to auto-activate the default commercial token
    if not token and settings.get("is_setup_completed") == "1":
        # Check if default token is valid and initialize it
        valid, msg, payload = verify_license_token(DEFAULT_COMMERCIAL_LICENSE_TOKEN)
        if valid:
            token = DEFAULT_COMMERCIAL_LICENSE_TOKEN
            save_license_token(token, conn)
            settings["license_token"] = token

    if not token:
        return {
            "status": "UNLICENSED",
            "is_valid": False,
            "message": "No commercial license installed. Please activate a valid commercial license.",
            "license_id": None,
            "licensee_name": settings.get("org_name", "Unlicensed"),
            "tier": "UNLICENSED",
            "max_branches": 0,
            "expires_at": None,
            "features": []
        }

    is_valid, message, payload = verify_license_token(token)

    if not is_valid:
        status = "EXPIRED" if "expired" in message.lower() else "TAMPERED"
        return {
            "status": status,
            "is_valid": False,
            "message": message,
            "license_id": payload.get("license_id") if payload else None,
            "licensee_name": payload.get("licensee_name") if payload else settings.get("org_name", ""),
            "tier": payload.get("tier", "INVALID") if payload else "INVALID",
            "max_branches": int(payload.get("max_branches", 0)) if payload else 0,
            "expires_at": payload.get("expires_at") if payload else None,
            "features": payload.get("features", []) if payload else []
        }

    # Calculate days remaining
    try:
        exp_str = payload["expires_at"]
        if exp_str.endswith("Z"):
            exp_dt = datetime.fromisoformat(exp_str[:-1]).replace(tzinfo=timezone.utc)
        else:
            exp_dt = datetime.fromisoformat(exp_str).replace(tzinfo=timezone.utc)
        days_left = (exp_dt - datetime.now(timezone.utc)).days
    except Exception:
        days_left = 0

    return {
        "status": "ACTIVE",
        "is_valid": True,
        "message": f"Active Commercial License ({payload.get('tier', 'PRO')} Tier) — {days_left} days remaining",
        "license_id": payload["license_id"],
        "licensee_name": payload["licensee_name"],
        "tier": payload["tier"],
        "max_branches": int(payload["max_branches"]),
        "expires_at": payload["expires_at"],
        "features": payload.get("features", []),
        "days_left": max(0, days_left),
        "token": token
    }


def save_license_token(token: str, conn) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validates the token signature and writes it to system_settings on success.
    """
    is_valid, msg, payload = verify_license_token(token)
    if not is_valid:
        return False, msg, payload

    cur = conn.cursor()
    settings_to_store = [
        ("license_token", token.strip()),
        ("license_key", payload.get("license_id", "LIC-TOKEN")),
        ("license_status", f"Active ({payload.get('tier', 'PRO')} Tier - {payload.get('max_branches', 3)} Branches)"),
        ("license_tier", f"{payload.get('tier', 'PRO')} Tier"),
        ("license_branch_limit", str(payload.get("max_branches", 3))),
        ("license_valid_until", payload.get("expires_at", "")),
        ("org_name", payload.get("licensee_name", "Rajeshri Shahu Trading Co."))
    ]

    for k, v in settings_to_store:
        cur.execute("""
            INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at)
            VALUES ('SUPER_ADMIN', 'GLOBAL', ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(scope, scope_id, setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=CURRENT_TIMESTAMP
        """, (k, v))

    conn.commit()
    return True, "Commercial License activated successfully.", payload


def check_branch_limit(conn) -> Tuple[bool, str, int, int]:
    """
    Checks if active branch count is below the licensed maximum.
    Returns (is_allowed, error_message, current_count, max_limit).
    """
    lic = get_active_license(conn)
    if not lic["is_valid"]:
        return False, f"License is not active: {lic['message']}", 0, 0

    cur = conn.cursor()
    cur.execute("SELECT count(*) as cnt FROM branches WHERE is_active=1")
    current_count = cur.fetchone()["cnt"]
    max_branches = lic["max_branches"]

    if current_count >= max_branches:
        return False, f"Licensed branch limit reached ({current_count}/{max_branches} active branches). Upgrade license to add more branches.", current_count, max_branches

    return True, "Branch creation permitted within license limit.", current_count, max_branches
