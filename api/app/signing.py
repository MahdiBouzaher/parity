import base64
import hashlib
import json
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from . import config
from .hashing import sha256_bytes

ALGORITHM = "Ed25519"
_key = None


def canonical_bytes(obj):
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def raw_public(public_key):
    return public_key.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def fingerprint_of(raw):
    return sha256_bytes(raw)


def load_key():
    """Return this instance's private key, creating the key pair on first use."""
    global _key
    if _key is not None:
        return _key
    keys_dir = config.KEYS_DIR
    private_path = keys_dir / "signing_key.pem"
    if private_path.exists():
        key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    else:
        keys_dir.mkdir(parents=True, exist_ok=True)
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(pem)
        (keys_dir / "signing_key.pub.pem").write_bytes(
            key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    _key = key
    return key


def local_fingerprint():
    return fingerprint_of(raw_public(load_key().public_key()))


def sign_report(body):
    """Sign the canonical JSON of body (which must not hold a signature block)."""
    key = load_key()
    payload = canonical_bytes(body)
    public = raw_public(key.public_key())
    return {
        "algorithm": ALGORITHM,
        "payload_sha256": sha256_bytes(payload),
        "signature": base64.b64encode(key.sign(payload)).decode("ascii"),
        "public_key": base64.b64encode(public).decode("ascii"),
        "key_fingerprint": fingerprint_of(public),
        "signed_at": body.get("signed_at"),
    }


def verify_report(obj):
    """Check a signed report. Returns (ok, reason, fingerprint)."""
    block = obj.get("signature") if isinstance(obj, dict) else None
    if not isinstance(block, dict):
        return False, "There is no signature block.", None
    body = {k: v for k, v in obj.items() if k != "signature"}
    try:
        public = base64.b64decode(block["public_key"], validate=True)
        signature = base64.b64decode(block["signature"], validate=True)
        claimed = block["payload_sha256"]
        if block.get("algorithm") != ALGORITHM or len(public) != 32:
            raise ValueError
    except Exception:
        return False, "The signature block is malformed.", None
    fingerprint = fingerprint_of(public)
    if block.get("key_fingerprint") != fingerprint:
        return False, "The key fingerprint does not match the public key.", fingerprint
    payload = canonical_bytes(body)
    if sha256_bytes(payload) != claimed:
        return False, "The report content no longer matches its hash.", fingerprint
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature, payload)
    except InvalidSignature:
        return False, "The signature does not match the report.", fingerprint
    return True, None, fingerprint
