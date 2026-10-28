"""Explicit iSH network backend with operator-assisted IPv6 discovery.

Device-derived candidates are tried first; the operator can supply each new
system's IPv6 router address. Stock, RAM and permanent addresses are separate.
No multicast, Netlink, sysfs or iOS background-execution assumption is used.
"""
import ipaddress
import hashlib
import re
import shutil
import subprocess
import sys
import time

import ish_network as net


class ISHBackend:
    interface = "ish-wifi"

    def __init__(self, args, profile, log=print, resume=None):
        self.args = args
        self.profile = profile
        self.log = log
        self.phase = "ram"
        self.ssid = profile.installer_wifi_ssid
        self.scp_flags = ["-O"]
        self.art_sha256 = (resume or {}).get("ish_art_sha256")
        self.art_size = (resume or {}).get("ish_art_size")
        self.device_addresses = (resume or {}).get("ish_device_addresses", [])
        if not isinstance(self.device_addresses, list):
            raise net.NetworkCheckError("invalid recorded iSH device addresses")
        for address in self.device_addresses:
            if not ipaddress.IPv6Address(address).is_link_local or "%" in address:
                raise net.NetworkCheckError("invalid recorded iSH device address")
        self.candidates = {"ram": args.ish_ram_address,
                           "permanent": args.ish_permanent_address}
        if not 1 <= args.ish_scope_max <= 256:
            raise net.NetworkCheckError("--ish-scope-max must be 1..256")

    def require_runtime(self):
        missing = [name for name in ("ssh", "scp", "sshpass", "openssl") if not shutil.which(name)]
        if missing:
            raise net.NetworkCheckError(
                "missing " + ", ".join(missing) +
                "; in iSH run: apk add openssh-client sshpass openssl ca-certificates")
        if not sys.stdin.isatty():
            raise net.NetworkCheckError(
                "live iSH installation requires a foreground interactive terminal")
        try:
            result = subprocess.run(["ssh", "-V"], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError) as exc:
            raise net.NetworkCheckError("cannot run the local OpenSSH version check") from exc
        match = re.search(r"OpenSSH_(\d+)\.(\d+)", result.stdout + result.stderr)
        if result.returncode != 0 or not match:
            raise net.NetworkCheckError("expected an OpenSSH client from openssh-client")
        version = tuple(map(int, match.groups()))
        # OpenSSH <=8.6 uses legacy SCP and has no -O option. >=8.7 can
        # explicitly select it; >=9 defaults to SFTP without that option.
        self.scp_flags = ["-O"] if version >= (8, 7) else []
        self.log(f"[*] OpenSSH {version[0]}.{version[1]}: legacy SCP selected")

    def transport(self, interface):
        if interface != self.interface:
            raise net.NetworkCheckError("iSH requires logical interface ish-wifi")
        return "wifi"

    def callback_address(self, host, override):
        source = net.callback_source(host, override)
        if not self.args.ish_stock_ipv6:
            raise net.NetworkCheckError(
                "provide --ish-stock-ipv6 fe80::ADDRESS%NUMBER from the read-only phone check")
        left = net.read_stock_identity(host, include_identifiers=True)
        right = net.read_stock_identity6(
            self.args.ish_stock_ipv6, host, include_identifiers=True)
        net.require_same_stock_device(left, right)
        if (left.get("hardware") not in self.profile.stock_hardware
                or left.get("model") != self.profile.stock_model
                or left.get("romversion") not in self.profile.tested_stock_roms):
            raise net.NetworkCheckError("unsupported stock identity")
        net.check_listeners(source, (self.args.serve_port, self.args.shell_port,
                                     self.args.file_port))
        self.log("[*] native source and stock IPv4/IPv6 identity checks passed")
        return source

    def set_phase(self, phase, ssid=None):
        if phase not in ("ram", "permanent"):
            raise net.NetworkCheckError("invalid iSH discovery phase")
        self.phase = phase
        self.ssid = ssid or (self.profile.installer_wifi_ssid if phase == "ram" else None)

    def validate_peer(self, host):
        # A Linux default-gateway check cannot run in iSH. Restrict every
        # authenticated target to an explicitly scoped IPv6 link-local peer.
        net.parse_scoped_linklocal(host)

    def record_backup(self, ch, path, partition, manifest_path):
        """Verify the received ART backup against the same stock root channel.

        Current RD03v2 DTS reads LAN MAC from ART offset 6. Its EUI-64 is
        a candidate, not proof of the future bridge address or router identity.
        """
        import install
        with open(path, "rb") as source:
            blob = source.read()
        if len(blob) != partition["size"] or len(blob) < 12:
            raise net.NetworkCheckError("ART backup length differs from the stock partition")
        rc, output = ch.run(f"md5sum /dev/mtd{int(partition['index'])}", quiet=True)
        if rc != 0 or not output.split() or output.split()[0] != hashlib.md5(blob).hexdigest():
            raise net.NetworkCheckError("ART backup does not match the stock partition")
        mac = bytearray(blob[6:12])
        if mac[0] & 1 or mac == bytearray(6):
            raise net.NetworkCheckError("ART contains an unusable LAN MAC")
        mac[0] ^= 2
        iid = mac[:3] + b"\xff\xfe" + mac[3:]
        candidate = str(ipaddress.IPv6Address(b"\xfe\x80" + b"\x00"*6 + iid))
        self.art_sha256 = hashlib.sha256(blob).hexdigest()
        self.art_size = len(blob)
        self.device_addresses = [candidate]
        install.update_resume_fields(manifest_path, ish_art_sha256=self.art_sha256,
                                     ish_art_size=self.art_size, ish_device_addresses=[candidate])
        self.log("[*] ART backup matches stock; RAM discovery candidate saved privately")

    def verify_device(self, host, mtd, ssh):
        """Check the original unit's ART before sysupgrade and final success."""
        self.validate_peer(host)
        if (not isinstance(self.art_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", self.art_sha256) is None
                or type(self.art_size) is not int or self.art_size < 12):
            raise net.NetworkCheckError("missing original ART identity record; refusing iSH install")
        parts = [part for name, part in mtd.items() if name.lower() == "0:art"]
        if len(parts) != 1 or parts[0]["size"] != self.art_size:
            raise net.NetworkCheckError("ART partition does not match the original device")
        rc, output = ssh(host, f"sha256sum /dev/mtd{int(parts[0]['index'])}", check=False)
        if rc != 0 or not output.split() or output.split()[0] != self.art_sha256:
            raise net.NetworkCheckError("ART fingerprint differs from the original device")
        self.log("[*] original device ART fingerprint matched")

    def discover(self, deadline_s):
        end = time.monotonic() + deadline_s
        candidate = self.candidates[self.phase]
        self.log(f"[*] iSH {self.phase}: join Wi-Fi SSID {self.ssid!r} in Settings, then return here")
        self.log("[*] use the IPv6 Router address shown for that Wi-Fi; do not reuse a guessed address")
        while time.monotonic() < end:
            if not candidate and self.device_addresses:
                found = []
                for address in self.device_addresses:
                    try:
                        found.append(net.discover_unicast(
                            address, scopes=range(1, self.args.ish_scope_max+1),
                            timeout=min(2, max(0.1, end-time.monotonic()))))
                    except net.NetworkCheckError:
                        pass
                if len(found) == 1:
                    self.candidates[self.phase] = found[0].split("%", 1)[0]
                    return found[0]
                if len(found) > 1:
                    raise net.NetworkCheckError("multiple device-derived peers; manual inspection required")
            if not candidate:
                candidate = input("IPv6 router address (q to stop safely): ").strip()
            if candidate.lower() == "q":
                raise net.NetworkCheckError("stopped; continue with the private resume.json")
            try:
                if "%" in candidate:
                    address, scope = net.parse_scoped_linklocal(candidate)
                    scopes = (scope,)
                else:
                    address = str(ipaddress.IPv6Address(candidate))
                    scopes = range(1, self.args.ish_scope_max + 1)
                peer = net.discover_unicast(address, scopes=scopes,
                                           timeout=min(2, max(0.1, end-time.monotonic())))
                # Retain address only; future discovery rescans native scopes.
                self.candidates[self.phase] = address
                self.log(f"[*] single scoped Dropbear peer found: {peer}; identity still needs checking")
                return peer
            except (ValueError, net.NetworkCheckError) as exc:
                self.log(f"[*] not ready: {exc}")
                if not sys.stdin.isatty():
                    raise net.NetworkCheckError("discovery needs an interactive terminal") from exc
                replacement = input("Return to retry, enter a corrected IPv6 address, or q: ").strip()
                candidate = replacement or candidate
        raise net.NetworkCheckError("iSH discovery timed out; keep power on and resume later")


def options(network):
    """Keep Linux callers and their public function signatures compatible."""
    return {"network": network} if network is not None else {}
