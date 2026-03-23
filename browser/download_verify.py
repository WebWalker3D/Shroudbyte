"""Download cryptographic verification — check hashes and signatures."""

import hashlib
import json
import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class VerificationResult:
    """Result of a download verification check."""
    filename: str
    file_size: int
    sha256: str
    verified: bool = False
    method: str = ""  # "hash", "sigstore", "gpg", "unknown"
    signer: str = ""
    details: str = ""


def compute_hashes(file_path: str | Path) -> dict:
    """Compute SHA-256, SHA-512, and MD5 hashes of a file."""
    path = Path(file_path)
    if not path.exists():
        return {}

    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    md5 = hashlib.md5()

    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
            sha512.update(chunk)
            md5.update(chunk)

    return {
        "sha256": sha256.hexdigest(),
        "sha512": sha512.hexdigest(),
        "md5": md5.hexdigest(),
    }


def verify_hash(file_path: str | Path, expected_hash: str,
                algorithm: str = "sha256") -> VerificationResult:
    """Verify a file against an expected hash."""
    path = Path(file_path)
    hashes = compute_hashes(path)

    result = VerificationResult(
        filename=path.name,
        file_size=path.stat().st_size if path.exists() else 0,
        sha256=hashes.get("sha256", ""),
    )

    algo_map = {"sha256": "sha256", "sha512": "sha512", "md5": "md5"}
    algo = algo_map.get(algorithm.lower(), "sha256")
    actual = hashes.get(algo, "")

    if actual and actual.lower() == expected_hash.lower().strip():
        result.verified = True
        result.method = "hash"
        result.details = f"{algo} match"
    else:
        result.verified = False
        result.method = "hash"
        result.details = f"{algo} mismatch: expected {expected_hash[:16]}... got {actual[:16]}..."

    return result


def verify_sigstore(file_path: str | Path, bundle_path: str | Path | None = None) -> VerificationResult:
    """Verify a file using Sigstore/cosign attestation (if available)."""
    path = Path(file_path)
    hashes = compute_hashes(path)

    result = VerificationResult(
        filename=path.name,
        file_size=path.stat().st_size if path.exists() else 0,
        sha256=hashes.get("sha256", ""),
    )

    # Check for cosign binary
    import shutil
    cosign = shutil.which("cosign")
    if not cosign:
        result.method = "sigstore"
        result.details = "cosign not installed"
        return result

    # Look for .sig or .bundle file
    if bundle_path is None:
        for ext in [".sig", ".bundle", ".cosign.bundle"]:
            candidate = Path(str(path) + ext)
            if candidate.exists():
                bundle_path = candidate
                break

    if bundle_path is None:
        result.method = "sigstore"
        result.details = "No signature bundle found"
        return result

    import subprocess
    try:
        proc = subprocess.run(
            [cosign, "verify-blob", "--bundle", str(bundle_path), str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode == 0:
            result.verified = True
            result.method = "sigstore"
            result.signer = _extract_signer(proc.stdout)
            result.details = "Sigstore verification passed"
        else:
            result.method = "sigstore"
            result.details = f"Verification failed: {proc.stderr[:200]}"
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        result.method = "sigstore"
        result.details = str(e)

    return result


def _extract_signer(output: str) -> str:
    """Extract signer identity from cosign output."""
    for line in output.splitlines():
        if "Subject:" in line or "Issuer:" in line:
            return line.strip()
    return ""


def save_verification_receipt(result: VerificationResult, receipt_dir: str | Path):
    """Save a verification receipt for audit purposes."""
    receipt_dir = Path(receipt_dir)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    receipt = {
        "filename": result.filename,
        "file_size": result.file_size,
        "sha256": result.sha256,
        "verified": result.verified,
        "method": result.method,
        "signer": result.signer,
        "details": result.details,
    }

    import time
    receipt_path = receipt_dir / f"{result.filename}.{int(time.time())}.json"
    with open(receipt_path, "w") as f:
        json.dump(receipt, f, indent=2)
    return receipt_path
