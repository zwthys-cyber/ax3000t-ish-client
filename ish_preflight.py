#!/usr/bin/env python3
"""Read-only iSH preflight prototype. No install, reset or exploit commands."""
import argparse
import http.client
import json
import os
import tempfile

import ish_network


def check_state_storage(directory="."):
    """Exercise the real atomic resume writer on this filesystem, locally.

    Uses a private temporary folder and deletes it afterwards. Nothing is
    sent to the router, and a failed fsync is not silently bypassed.
    """
    import install
    with tempfile.TemporaryDirectory(prefix=".ish-state-check-", dir=directory) as root:
        path = os.path.join(root, "resume.json")
        install._write_resume_data(path, {"version": 1, "phase": "probe-started"})
        install.update_resume_phase(path, "probe-finished")
        if (install.load_resume_manifest(path).get("phase") != "probe-finished"
                or os.stat(path).st_mode & 0o777 != 0o600):
            raise ish_network.NetworkCheckError("resume state or file permissions failed")
    return "passed"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="192.168.31.1")
    ap.add_argument("--attacker", default=None)
    ap.add_argument("--stock-ipv6", default=None,
                    help="explicit link-local address with native numeric scope")
    ap.add_argument("--runtime", action="store_true",
                    help="also check local SSH tools and durable resume-file storage")
    args = ap.parse_args(argv)
    result = {"flash_ready": False, "checks": {}, "not_verified": [
        "router-to-phone callback", "RAM system discovery after Wi-Fi switch",
        "permanent system verification", "iOS suspension and resume"]}
    checks = result["checks"]
    try:
        if args.runtime:
            import install
            backend = install.ISHBackend(install.parse_args(["--network-backend", "ish"]),
                                         install.devices.RD03V2, log=lambda _: None)
            backend.require_runtime()
            checks["scp_options"] = backend.scp_flags
            checks["resume_storage"] = check_state_storage()
        source = ish_network.callback_source(args.host, args.attacker)
        checks["source"] = source
        checks["local_listener_ports"] = ish_network.check_listeners(source)
        identity = ish_network.read_stock_identity(
            args.host, include_identifiers=bool(args.stock_ipv6))
        checks["stock_identity"] = {
            key: identity.get(key) for key in ish_network.PUBLIC_IDENTITY_FIELDS}
        if (identity.get("hardware") != "RD03v2"
                or identity.get("model") != "xiaomi.router.rd03v2"
                or identity.get("romversion") != "2.0.28"
                or identity.get("code") != 0):
            raise ish_network.NetworkCheckError("not the expected RD03v2 stock 2.0.28")
        if args.stock_ipv6:
            other = ish_network.read_stock_identity6(
                args.stock_ipv6, args.host, include_identifiers=True)
            ish_network.require_same_stock_device(identity, other)
            checks["ipv4_ipv6_same_device"] = True
        checks["read_only_preflight"] = "passed"
    except (OSError, ValueError, http.client.HTTPException, ish_network.NetworkCheckError) as exc:
        checks["error"] = str(exc)
    print(json.dumps(result, indent=2))
    # A successful read-only test never implies install readiness.
    return 0 if checks.get("read_only_preflight") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
