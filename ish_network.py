"""Socket-based building blocks for iSH; never run an exploit or write flash.

Selected explicitly by install.py's experimental iSH backend. Router-to-phone
callbacks and iOS suspension/recovery are not validated on the target phone.
"""
import ipaddress
import http.client
import json
import socket
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor


class NetworkCheckError(RuntimeError):
    pass


def usable_ipv4(value):
    try:
        address = ipaddress.IPv4Address(value)
    except (ValueError, TypeError) as exc:
        raise NetworkCheckError("expected numeric IPv4") from exc
    if (address.is_unspecified or address.is_loopback or address.is_multicast
            or address.is_reserved or address == ipaddress.IPv4Address("255.255.255.255")):
        raise NetworkCheckError("expected usable unicast IPv4")
    return str(address)


def callback_source(host, requested=None):
    """Ask native routing for its IPv4 source, then validate a local bind.

    UDP connect sends no datagram. This proves local source selection only,
    not that the target is reachable or can connect back. No interface name,
    netmask, transport type or router identity is inferred from the result.
    """
    host = usable_ipv4(host)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((host, 9))
        source = usable_ipv4(sock.getsockname()[0])
    if source == host:
        raise NetworkCheckError("target is this device's selected source address")
    if requested is not None and usable_ipv4(requested) != source:
        raise NetworkCheckError("requested callback differs from selected source")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((source, 0))
    return source


def check_listeners(source, ports=(8000, 4444, 4445)):
    """Check binds together; close every listener even if a later bind fails."""
    source = usable_ipv4(source)
    listeners = []
    try:
        for port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listeners.append(sock)
            sock.bind((source, port))
            sock.listen(1)
        return list(ports)
    finally:
        for sock in listeners:
            sock.close()


PUBLIC_IDENTITY_FIELDS = ("hardware", "model", "romversion", "code")
PRIVATE_IDENTITY_FIELDS = ("id", "routerId")


def decode_identity(raw, include_identifiers=False):
    if len(raw) > 131072:
        raise NetworkCheckError("identity response exceeds size limit")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise NetworkCheckError("identity response is not an object")
    fields = PUBLIC_IDENTITY_FIELDS
    if include_identifiers:
        fields += PRIVATE_IDENTITY_FIELDS
    return {key: data.get(key) for key in fields}


def read_stock_identity(host, include_identifiers=False):
    host = usable_ipv4(host)
    # Ignore proxy environment and disallow redirection to another device.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    url = "http://" + host + "/cgi-bin/luci/api/xqsystem/init_info"
    with opener.open(url, timeout=10) as response:
        raw = response.read(131073)
    return decode_identity(raw, include_identifiers)


def parse_scoped_linklocal(value):
    """Accept an explicit numeric scope only; no Linux interface-name ioctls."""
    try:
        address, scope = value.rsplit("%", 1)
        if "%" in address:
            raise ValueError("multiple scopes")
        address = ipaddress.IPv6Address(address)
        if not scope.isascii() or not scope.isdecimal():
            raise ValueError("non-numeric scope")
        scope = int(scope)
        if not address.is_link_local or not 0 < scope < 2**32:
            raise ValueError("invalid address or scope")
    except (AttributeError, ValueError) as exc:
        raise NetworkCheckError("expected fe80:: address with native numeric %scope") from exc
    return str(address), scope


def check_linklocal_tcp(value, port=80, timeout=2):
    """Capability test only, never router identity or proof of flash readiness."""
    address, scope = parse_scoped_linklocal(value)
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((address, port, 0, scope))


def read_stock_identity6(value, http_host="192.168.31.1", include_identifiers=False):
    """Direct numeric-scope HTTP without DNS, proxy or redirect handling.

    Preserve the stock service's IPv4 Host header while connecting via IPv6.
    Identifiers are optional, used only for local cross-address comparison.
    """
    address, scope = parse_scoped_linklocal(value)
    http_host = usable_ipv4(http_host)
    connection = http.client.HTTPConnection(http_host, timeout=10)
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
            sock.settimeout(10)
            sock.connect((address, 80, 0, scope))
            connection.sock = sock
            connection.request("GET", "/cgi-bin/luci/api/xqsystem/init_info",
                               headers={"Connection": "close"})
            response = connection.getresponse()
            if response.status != 200:
                raise NetworkCheckError("IPv6 identity HTTP status is not 200")
            return decode_identity(response.read(131073), include_identifiers)
    finally:
        connection.close()


def require_same_stock_device(ipv4_identity, ipv6_identity):
    """Fail if models match but IDs differ, or no ID can be compared.

    These unauthenticated HTTP IDs detect accidental selection of a different
    device; they are not cryptographic attestation against a hostile peer.
    Never put the ID values in errors/logs.
    """
    for key in PUBLIC_IDENTITY_FIELDS:
        if ipv4_identity.get(key) != ipv6_identity.get(key):
            raise NetworkCheckError("IPv4/IPv6 device metadata differs")
    if ipv4_identity.get("code") != 0:
        raise NetworkCheckError("stock identity request was not successful")
    compared = 0
    for key in PRIVATE_IDENTITY_FIELDS:
        left, right = ipv4_identity.get(key), ipv6_identity.get(key)
        if left is None and right is None:
            continue
        if not isinstance(left, str) or not left.strip() or left != right:
            raise NetworkCheckError("IPv4/IPv6 device identifiers differ or are missing")
        compared += 1
    if not compared:
        raise NetworkCheckError("no device identifier available for comparison")
    return True


def discover_unicast(address, scopes=range(1, 65), timeout=2):
    """Find a Dropbear banner at one explicit link-local, without multicast.

    Rescan native scopes each time, rather than retaining a stale iOS interface
    number across Wi-Fi changes. Exactly one scoped peer must answer. This is
    discovery only: board/rootfs/NAND identity checks remain mandatory before
    treating a discovered peer as an installation target.

    The address must come from the operator or validated device data. Stock's
    address is not assumed to survive a reboot into another system.
    """
    try:
        parsed = ipaddress.IPv6Address(address)
    except (ValueError, TypeError) as exc:
        raise NetworkCheckError("expected an explicit IPv6 link-local address") from exc
    if not parsed.is_link_local or "%" in str(parsed):
        raise NetworkCheckError("expected an unscoped IPv6 link-local address")
    address = str(parsed)
    scopes = tuple(scopes)
    if not scopes or len(scopes) > 256:
        raise NetworkCheckError("expected 1 to 256 explicit native scopes")
    if any(type(scope) is not int or not 0 < scope < 2**32 for scope in scopes):
        raise NetworkCheckError("invalid native scope")
    scopes = tuple(dict.fromkeys(scopes))
    if not 0 < timeout <= 10:
        raise NetworkCheckError("discovery timeout must be positive and at most 10 seconds")

    def probe(scope):
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
                deadline = time.monotonic() + timeout
                sock.settimeout(timeout)
                sock.connect((address, 22, 0, scope))
                # Never send an SSH username, password, command or packet.
                # recv can be fragmented, so collect one bounded banner line.
                banner = bytearray()
                while len(banner) < 255:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                    sock.settimeout(remaining)
                    chunk = sock.recv(1)
                    if not chunk:
                        return None
                    banner += chunk
                    if chunk == b"\n":
                        break
                if (banner.endswith(b"\n")
                        and banner.startswith(b"SSH-2.0-dropbear")
                        and banner[len(b"SSH-2.0-dropbear"):][:1] in (b"_", b"\r", b"\n")):
                    return f"{address}%{scope}"
        except OSError:
            pass
        return None

    with ThreadPoolExecutor(max_workers=min(8, len(scopes))) as pool:
        found = [peer for peer in pool.map(probe, scopes) if peer]
    if len(found) != 1:
        raise NetworkCheckError(
            "expected exactly one scoped Dropbear peer; found " + str(len(found)))
    return found[0]
