"""Safety regressions for the experimental, read-only iSH client."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import ish_network as net
import ish_preflight
import install


class NetworkChecks(unittest.TestCase):
    def test_source_must_match_requested_callback(self):
        with patch.object(net.socket, "socket") as factory:
            udp = factory.return_value.__enter__.return_value
            udp.getsockname.return_value = ("192.168.31.28", 43210)
            with self.assertRaises(net.NetworkCheckError):
                net.callback_source("192.168.31.1", "192.168.31.29")
            self.assertEqual(factory.call_count, 1)
            udp.send.assert_not_called()
            udp.sendto.assert_not_called()

    def test_target_must_not_be_own_address(self):
        with patch.object(net.socket, "socket") as factory:
            factory.return_value.__enter__.return_value.getsockname.return_value = (
                "192.168.31.28", 43210)
            with self.assertRaises(net.NetworkCheckError):
                net.callback_source("192.168.31.28")

    def test_native_route_failure_is_not_hidden(self):
        with patch.object(net.socket, "socket") as factory:
            factory.return_value.__enter__.return_value.connect.side_effect = OSError(
                113, "Host is unreachable")
            with self.assertRaises(OSError):
                net.callback_source("192.168.31.1")

    def test_reject_non_unicast_or_nonnumeric_without_socket(self):
        with patch.object(net.socket, "socket") as factory:
            for value in ("0.0.0.0", "127.0.0.1", "224.0.0.1", "255.255.255.255",
                          "::1", "router.local", "192.168.31.1/path"):
                with self.subTest(value=value), self.assertRaises(net.NetworkCheckError):
                    net.callback_source(value)
            factory.assert_not_called()

    def test_all_listeners_closed_on_bind_failure(self):
        first, second = MagicMock(), MagicMock()
        second.bind.side_effect = OSError("in use")
        with patch.object(net.socket, "socket", side_effect=[first, second]):
            with self.assertRaises(OSError):
                net.check_listeners("192.168.31.28")
        first.close.assert_called_once()
        second.close.assert_called_once()

    def test_reject_invalid_scoped_destinations_before_connect(self):
        with patch.object(net.socket, "socket") as factory:
            for value in ("fe80::1", "fe80::1%en0", "fe80::1%0", "fe80::1%-1",
                          "fe80::1%4294967296", "ff02::1%4", "::1%4", "fe80::1%４",
                          "fe80::1%en0%24"):
                with self.subTest(value=value), self.assertRaises(net.NetworkCheckError):
                    net.check_linklocal_tcp(value)
            factory.assert_not_called()

    def test_explicit_numeric_scope_reaches_native_socket(self):
        with patch.object(net.socket, "socket") as factory:
            net.check_linklocal_tcp("fe80::1234%7")
            factory.return_value.__enter__.return_value.connect.assert_called_once_with(
                ("fe80::1234", 80, 0, 7))

    def test_oversized_identity_is_rejected(self):
        with patch.object(net.urllib.request, "build_opener") as build:
            build.return_value.open.return_value.__enter__.return_value.read.return_value = (
                b" " * 131073)
            with self.assertRaises(net.NetworkCheckError):
                net.read_stock_identity("192.168.31.1")

    def test_preflight_success_never_reports_flash_ready(self):
        identity = dict(hardware="RD03v2", model="xiaomi.router.rd03v2",
                        romversion="2.0.28", code=0)
        with patch.object(net, "callback_source", return_value="192.168.31.28"), \
             patch.object(net, "check_listeners", return_value=[8000, 4444, 4445]), \
             patch.object(net, "read_stock_identity", return_value=identity), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(ish_preflight.main([]), 0)
        report = json.loads(out.getvalue())
        self.assertFalse(report["flash_ready"])
        self.assertTrue(report["not_verified"])

    def test_wrong_hardware_fails_readonly_preflight(self):
        identity = dict(hardware="RD03", model="xiaomi.router.rd03", romversion="2.0.28", code=0)
        with patch.object(net, "callback_source", return_value="192.168.31.28"), \
             patch.object(net, "check_listeners", return_value=[8000, 4444, 4445]), \
             patch.object(net, "read_stock_identity", return_value=identity), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(ish_preflight.main([]), 1)
        self.assertFalse(json.loads(out.getvalue())["flash_ready"])

    def test_same_model_different_device_is_rejected(self):
        left = dict(hardware="RD03v2", model="xiaomi.router.rd03v2",
                    romversion="2.0.28", code=0, id="unit-A", routerId="uuid-A")
        right = dict(left, id="unit-B", routerId="uuid-B")
        with self.assertRaises(net.NetworkCheckError) as error:
            net.require_same_stock_device(left, right)
        self.assertNotIn("unit-", str(error.exception))
        self.assertNotIn("uuid-", str(error.exception))

    def test_matching_ids_with_changed_metadata_are_rejected(self):
        left = dict(hardware="RD03v2", model="xiaomi.router.rd03v2",
                    romversion="2.0.28", code=0, id="same-unit")
        for right in (dict(left, romversion="2.0.12"), dict(left, code=1)):
            with self.assertRaises(net.NetworkCheckError):
                net.require_same_stock_device(left, right)

    def test_missing_identifiers_do_not_count_as_a_match(self):
        for identity in ({"code": 0}, {"code": 0, "id": ""},
                         {"code": 0, "id": "  "}, {"code": 0, "id": 123}):
            with self.assertRaises(net.NetworkCheckError):
                net.require_same_stock_device(identity, identity)

    def test_all_available_identifiers_must_match(self):
        left = dict(code=0, id="same-unit", routerId="uuid-A")
        right = dict(left, routerId="uuid-B")
        with self.assertRaises(net.NetworkCheckError):
            net.require_same_stock_device(left, right)
        self.assertTrue(net.require_same_stock_device(left, left))

    def test_ipv6_redirect_is_not_followed(self):
        with patch.object(net.socket, "socket"), \
             patch.object(net.http.client, "HTTPConnection") as factory:
            factory.return_value.getresponse.return_value.status = 302
            with self.assertRaises(net.NetworkCheckError):
                net.read_stock_identity6("fe80::1234%24")
            self.assertEqual(factory.return_value.request.call_count, 1)
            factory.return_value.close.assert_called_once()

    def test_verified_pair_report_never_contains_device_identifiers(self):
        identity = dict(hardware="RD03v2", model="xiaomi.router.rd03v2",
                        romversion="2.0.28", code=0, id="secret-unit-id", routerId="secret-router-id")
        with patch.object(net, "callback_source", return_value="192.168.31.28"), \
             patch.object(net, "check_listeners", return_value=[8000, 4444, 4445]), \
             patch.object(net, "read_stock_identity", return_value=identity), \
             patch.object(net, "read_stock_identity6", return_value=identity), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(ish_preflight.main([
                "--stock-ipv6", "fe80::1234%24"]), 0)
        report = json.loads(out.getvalue())
        self.assertTrue(report["checks"]["ipv4_ipv6_same_device"])
        self.assertFalse(report["flash_ready"])
        self.assertNotIn("secret-", out.getvalue())


class DiscoveryChecks(unittest.TestCase):
    def fake_network(self, peers):
        class FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def settimeout(self, timeout):
                pass

            def connect(self, destination):
                address, port, flowinfo, scope = destination
                if port != 22 or scope not in peers:
                    raise OSError("unreachable")
                self.data = iter(peers[scope])

            def recv(self, count):
                value = next(self.data, None)
                return bytes([value]) if value is not None else b""

        return patch.object(net.socket, "socket", side_effect=lambda *args: FakeSocket())

    def test_scopes_are_rescanned_after_network_change(self):
        with self.fake_network({24: b"SSH-2.0-dropbear_2024.86\r\n"}):
            self.assertEqual(net.discover_unicast("fe80::1234", scopes=(11, 24)),
                             "fe80::1234%24")
        with self.fake_network({11: b"SSH-2.0-dropbear_2024.86\r\n"}):
            self.assertEqual(net.discover_unicast("fe80::1234", scopes=(11, 24)),
                             "fe80::1234%11")

    def test_multiple_scoped_peers_are_rejected(self):
        with self.fake_network({11: b"SSH-2.0-dropbear_2024.86\r\n",
                                24: b"SSH-2.0-dropbear_2024.86\r\n"}):
            with self.assertRaises(net.NetworkCheckError):
                net.discover_unicast("fe80::1234", scopes=(11, 24))

    def test_wrong_or_incomplete_banner_is_rejected(self):
        for banner in (b"SSH-2.0-OpenSSH_9.1\r\n", b"SSH-2.0-dropbear-fake\r\n",
                       b"SSH-2.0-dropbear_2024", b"HTTP/1.1 200 OK\r\n",
                       b"SSH-2.0-dropbear_" + b"x" * 300 + b"\r\n"):
            with self.subTest(banner=banner), self.fake_network({24: banner}):
                with self.assertRaises(net.NetworkCheckError):
                    net.discover_unicast("fe80::1234", scopes=(24,))

    def test_invalid_discovery_inputs_send_nothing(self):
        with patch.object(net.socket, "socket") as factory:
            for address, scopes in (("192.168.1.1", (24,)), ("ff02::1", (24,)),
                                    ("fe80::1%24", (24,)), ("fe80::1", (True,)),
                                    ("fe80::1", (0,)), ("fe80::1", ())):
                with self.subTest(address=address, scopes=scopes), \
                     self.assertRaises(net.NetworkCheckError):
                    net.discover_unicast(address, scopes=scopes)
            factory.assert_not_called()


class PivotCheckpointChecks(unittest.TestCase):
    def test_rebooting_resume_dispatches_to_ram_without_stock_writes(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "resume.json")
            images = {kind: {"name": kind + "-wifi.bin", "sha256": "a" * 64}
                      for kind in ("initramfs_ubi", "initramfs_itb", "sysupgrade")}
            resume = dict(version=1, phase="pivot-rebooting", profile="rd03v2",
                          release="v-test", image="standard", flavour="default",
                          transport="wifi", interface="wlan0", verify_interface="wlan0",
                          images_dir=root, offline=True, images=images,
                          session_token="a" * 32, callback_address="192.168.31.28")
            install._write_resume_data(path, resume)
            rel = SimpleNamespace(tag="v-test", published="test", assets=["initramfs-wifi"])
            with patch.object(install, "detect_transport", return_value="wifi"), \
                 patch.object(install, "require_wifi_firstboot"), \
                 patch.object(install.release, "resolve", return_value=rel), \
                 patch.object(install.release, "get_images", return_value=images), \
                 patch.object(install, "wait_and_discover", return_value="fe80::1234%24"), \
                 patch.object(install, "flash") as flash, \
                 patch.object(install, "pivot") as pivot, \
                 patch.object(install.chain, "init_info") as stock, \
                 patch.object(install.chain, "plant") as plant, \
                 patch.object(install, "callback_address") as callback, \
                 patch.object(install.chain, "set_log_sink", side_effect=lambda fh: fh.close()), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install.main(["--resume-manifest", path]), 0)
                flash.assert_called_once()
                self.assertEqual(flash.call_args.args[0], "fe80::1234%24")
                pivot.assert_not_called()
                stock.assert_not_called()
                plant.assert_not_called()
                callback.assert_not_called()

    def test_disconnect_after_reboot_keeps_durable_uncertainty(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "resume.json")
            install._write_resume_data(path, {"version": 1, "phase": "preflight-complete"})
            ch = MagicMock()
            def disconnect(*args, **kwargs):
                self.assertEqual(install.load_resume_manifest(path)["phase"],
                                 "pivot-rebooting")
                raise OSError("socket disconnected after reboot request")
            ch.run.side_effect = disconnect
            with self.assertRaises(OSError):
                install.reboot_after_pivot(ch, path)
            self.assertEqual(install.load_resume_manifest(path)["phase"], "pivot-rebooting")
            self.assertEqual(ch.run.call_count, 1)
            self.assertEqual(ch.run.call_args.kwargs["retries"], 0)

    def test_checkpoint_failure_prevents_reboot(self):
        ch = MagicMock()
        with patch.object(install, "update_resume_phase", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                install.reboot_after_pivot(ch, "/no-write/resume.json")
        ch.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
