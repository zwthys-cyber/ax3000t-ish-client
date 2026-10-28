"""Model complete iSH driver dispatch; no real router or flash is contacted."""
import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import devices
import install
import ish_backend
import ish_network as net


def arguments(**changes):
    values = dict(ish_ram_address=None, ish_permanent_address=None, ish_scope_max=64,
                  ish_stock_ipv6="fe80::1234%24", serve_port=8000, shell_port=4444,
                  file_port=4445, wifi_ssid="PhoneNet")
    values.update(changes)
    return SimpleNamespace(**values)


class BackendUnitChecks(unittest.TestCase):
    def test_runtime_selects_old_and_new_scp_protocol_flags(self):
        for version, expected in (("8.6", []), ("8.7", ["-O"]), ("9.9", ["-O"])):
            backend = ish_backend.ISHBackend(arguments(), devices.RD03V2, log=lambda _: None)
            with self.subTest(version=version), \
                 patch.object(ish_backend.shutil, "which", return_value="/bin/tool"), \
                 patch.object(ish_backend.sys.stdin, "isatty", return_value=True), \
                 patch.object(ish_backend.subprocess, "run", return_value=SimpleNamespace(
                     returncode=0, stdout="", stderr="OpenSSH_" + version + "p1")):
                backend.require_runtime()
            self.assertEqual(backend.scp_flags, expected)

    def test_scp_ipv6_escaping_and_old_client_flag(self):
        backend = ish_backend.ISHBackend(arguments(), devices.RD03V2)
        backend.scp_flags = []
        with patch.object(install.shutil, "which", return_value="/bin/sshpass"), \
             patch.object(install.subprocess, "run", return_value=SimpleNamespace(
                 returncode=0, stdout="", stderr="")) as run:
            install.scp_to("fe80::1234%24", "/tmp/image", "/tmp/fw.bin", network=backend)
        argv = run.call_args.args[0]
        self.assertNotIn("-O", argv)
        self.assertEqual(argv[-1], "root@[fe80::1234%24]:/tmp/fw.bin")

    def test_ish_authenticated_peer_must_be_scoped_linklocal(self):
        backend = ish_backend.ISHBackend(arguments(), devices.RD03V2)
        with patch.object(install, "ssh_banner") as banner, \
             patch.object(install, "default_gateways", side_effect=AssertionError("Linux route lookup")):
            with self.assertRaises(net.NetworkCheckError):
                install.check_is_openwrt_ram("192.168.1.1", network=backend)
            banner.assert_not_called()
            banner.return_value = ("SSH-2.0-dropbear_2024.86", None)
            install.check_is_openwrt_ram("fe80::1234%24", network=backend)

    def test_ish_discovery_never_accepts_ipv4_fallback(self):
        backend = ish_backend.ISHBackend(arguments(), devices.RD03V2)
        with patch.object(backend, "discover") as discover:
            with self.assertRaises(install.Abort):
                install.wait_and_discover("ish-wifi", fallback="192.168.1.1", network=backend)
            discover.assert_not_called()

    def test_ram_address_is_not_reused_as_permanent_address(self):
        backend = ish_backend.ISHBackend(arguments(ish_ram_address="fe80::10"), devices.RD03V2,
                                          log=lambda _: None)
        with patch.object(net, "discover_unicast", side_effect=lambda address, **kw: address+"%7") as discover, \
             patch("builtins.input", return_value="fe80::20") as prompt:
            self.assertEqual(backend.discover(5), "fe80::10%7")
            backend.set_phase("permanent", "PhoneNet")
            self.assertEqual(backend.discover(5), "fe80::20%7")
        self.assertEqual([c.args[0] for c in discover.call_args_list], ["fe80::10", "fe80::20"])
        prompt.assert_called_once()

    def test_device_candidates_require_verified_art_backup(self):
        backend = ish_backend.ISHBackend(arguments(), devices.RD03V2, log=lambda _: None)
        blob = b"\x00"*6 + bytes.fromhex("020000000001") + b"\xff"*20
        with tempfile.TemporaryDirectory() as root:
            art = os.path.join(root, "art.bin")
            manifest = os.path.join(root, "resume.json")
            with open(art, "wb") as output:
                output.write(blob)
            install._write_resume_data(manifest, {"version": 1, "phase": "preflight-complete"})
            ch = MagicMock()
            ch.run.return_value = (0, "0"*32 + "  /dev/mtd5")
            with self.assertRaises(net.NetworkCheckError):
                backend.record_backup(ch, art, {"index": 5, "size": len(blob)}, manifest)
            self.assertNotIn("ish_art_sha256", install.load_resume_manifest(manifest))
            ch.run.return_value = (0, hashlib.md5(blob).hexdigest()+"  /dev/mtd5")
            backend.record_backup(ch, art, {"index": 5, "size": len(blob)}, manifest)
            record = install.load_resume_manifest(manifest)
            self.assertEqual(record["ish_device_addresses"], ["fe80::ff:fe00:1"])
            self.assertEqual(record["ish_art_sha256"], hashlib.sha256(blob).hexdigest())

    def test_factory_candidate_is_tried_without_requiring_settings_address(self):
        backend = ish_backend.ISHBackend(arguments(), devices.RD03V2, log=lambda _: None,
                                          resume={"ish_device_addresses": ["fe80::1234"]})
        with patch.object(net, "discover_unicast", return_value="fe80::1234%11"), \
             patch("builtins.input", side_effect=AssertionError("unneeded prompt")):
            self.assertEqual(backend.discover(5), "fe80::1234%11")

    def test_art_identity_must_match_original_before_write(self):
        backend = ish_backend.ISHBackend(arguments(), devices.RD03V2, log=lambda _: None,
                                          resume={"ish_art_sha256": "a"*64, "ish_art_size": 1024})
        mtd = {"0:art": {"index": 3, "size": 1024}}
        ssh = MagicMock(return_value=(0, "b"*64 + "  /dev/mtd3"))
        with self.assertRaises(net.NetworkCheckError):
            backend.verify_device("fe80::1234%24", mtd, ssh)
        ssh.return_value = (0, "a"*64 + "  /dev/mtd3")
        backend.verify_device("fe80::1234%24", mtd, ssh)
        with self.assertRaises(net.NetworkCheckError):
            backend.verify_device("fe80::1234%24", {"0:art": {"index": 3, "size": 2048}}, ssh)

    def test_missing_art_identity_stops_before_ssh(self):
        backend = ish_backend.ISHBackend(arguments(), devices.RD03V2)
        ssh = MagicMock()
        with self.assertRaises(net.NetworkCheckError):
            backend.verify_device("fe80::1234%24", {"0:art": {"index": 3, "size": 1024}}, ssh)
        ssh.assert_not_called()

    def test_local_state_storage_exercises_atomic_writer_and_cleanup(self):
        import ish_preflight
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(ish_preflight.check_state_storage(root), "passed")
            self.assertEqual(os.listdir(root), [])
            with patch.object(install.os, "fsync", side_effect=OSError("unsupported fsync")):
                with self.assertRaises(OSError):
                    ish_preflight.check_state_storage(root)
            self.assertEqual(os.listdir(root), [])


class DriverChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.manifest = os.path.join(self.root, "resume.json")
        self.images = {kind: {"name": kind + "-wifi.bin", "sha256": "a"*64,
                              "path": os.path.join(self.root, kind)}
                       for kind in ("initramfs_ubi", "initramfs_itb", "sysupgrade")}
        self.identity = dict(hardware="RD03v2", model="xiaomi.router.rd03v2", romversion="2.0.28",
                             code=0, id="private-unit-id", routerId="private-router-id", inited=1)
        self.rel = SimpleNamespace(tag="v-test", published="test", assets=["initramfs-wifi"])
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(install.chain, "set_log_sink", side_effect=lambda fh: fh.close()))
        self.runtime = self.stack.enter_context(patch.object(ish_backend.ISHBackend, "require_runtime"))
        self.resolve = self.stack.enter_context(patch.object(install.release, "resolve", return_value=self.rel))
        self.stack.enter_context(patch.object(install.release, "get_images", return_value=self.images))
        # Any hidden fallback to Linux route or sysfs inspection is a failure.
        self.stack.enter_context(patch.object(install.chain, "local_interface",
                                              side_effect=AssertionError("Linux route lookup")))
        self.stack.enter_context(patch.object(install, "interface_ipv4_networks",
                                              side_effect=AssertionError("Linux addr lookup")))

    def resume(self, phase):
        cfg = os.path.join(self.root, "cfg.tar.gz")
        with open(cfg, "wb") as output:
            output.write(b"model configuration")
        data = dict(version=1, phase=phase, profile="rd03v2", release="v-test",
                    image="standard", flavour="default", transport="wifi",
                    interface="ish-wifi", verify_interface="ish-wifi", images_dir=self.root,
                    offline=True, images={k: {"name": v["name"], "sha256": v["sha256"]}
                                          for k, v in self.images.items()},
                    session_token="a"*32, callback_address="192.168.31.28", config_tar=cfg,
                    wifi_ssid="PhoneNet", network_backend="ish", ish_stock_ipv6="fe80::1234%24",
                    stock_host="192.168.31.1", stock_wifi_restore=[dict(ssid="Original", encryption="none")])
        data.update(ish_art_sha256="b"*64, ish_art_size=1048576)
        install._write_resume_data(self.manifest, data)

    def test_ish_dry_run_has_no_router_or_runtime_access(self):
        with patch.object(install, "expected_volume", return_value=(b"test", "a"*32)), \
             patch.object(net, "callback_source") as source, \
             patch.object(install.chain, "init_info") as info:
            self.assertEqual(install.main(["--network-backend", "ish", "--dry-run",
                                           "--outdir", self.root]), 0)
        self.runtime.assert_not_called()
        source.assert_not_called()
        info.assert_not_called()
        self.assertFalse(os.path.exists(self.manifest))

    def test_ish_pivot_resume_dispatches_via_native_discovery(self):
        self.resume("pivot-rebooting")
        with patch.object(install, "require_wifi_firstboot"), \
             patch.object(ish_backend.ISHBackend, "discover", return_value="fe80::200%11") as discover, \
             patch.object(install, "flash") as flash, \
             patch.object(install, "pivot") as pivot, \
             patch.object(install.chain, "trigger") as trigger:
            self.assertEqual(install.main(["--resume-manifest", self.manifest]), 0)
        discover.assert_called_once()
        self.assertEqual(flash.call_args.args[0], "fe80::200%11")
        self.assertIsInstance(flash.call_args.kwargs["network"], ish_backend.ISHBackend)
        pivot.assert_not_called()
        trigger.assert_not_called()

    def test_ish_flash_started_resume_only_verifies(self):
        self.resume("flash-started")
        with patch.object(install, "verify_permanent_system") as verify, \
             patch.object(install, "flash") as flash, \
             patch.object(install.chain, "trigger") as trigger:
            self.assertEqual(install.main(["--resume-manifest", self.manifest]), 0)
        verify.assert_called_once()
        self.assertIsInstance(verify.call_args.kwargs["network"], ish_backend.ISHBackend)
        flash.assert_not_called()
        trigger.assert_not_called()
        self.resolve.assert_not_called()
        self.assertEqual(install.load_resume_manifest(self.manifest)["phase"], "flash-complete")

    def test_backend_change_on_resume_is_refused(self):
        self.resume("pivot-complete")
        with self.assertRaises(install.Abort):
            install.main(["--resume-manifest", self.manifest, "--network-backend", "linux"])
        self.runtime.assert_not_called()

    def preflight_patches(self):
        self.stack.enter_context(patch.object(net, "callback_source", return_value="192.168.31.28"))
        self.stack.enter_context(patch.object(net, "check_listeners"))
        self.stack.enter_context(patch.object(net, "read_stock_identity", return_value=self.identity))
        self.stack.enter_context(patch.object(net, "read_stock_identity6", return_value=self.identity))
        self.stack.enter_context(patch.object(install.chain, "init_info", return_value=self.identity))
        self.stack.enter_context(patch.object(install.chain, "port_open", return_value=True))
        self.stack.enter_context(patch.object(install.chain, "admin_session", return_value=("token", {})))
        self.stack.enter_context(patch.object(install.chain, "require_cap_sink_ready"))
        self.stack.enter_context(patch.object(install.chain, "read_wifi", return_value=[]))
        server = self.stack.enter_context(patch.object(install.channel, "StagerServer"))
        server.return_value.stager_path = "/token/s"
        ch = self.stack.enter_context(patch.object(install.channel, "ShellChannel"))
        ch.return_value.wait.return_value = True
        ch.return_value.run.return_value = (0, "uid=0(root)")
        self.stack.enter_context(patch.object(install, "preflight", return_value={}))
        return server

    def test_trigger_intent_is_saved_before_trigger(self):
        self.preflight_patches()
        def inspect(*args):
            state = install.load_resume_manifest(self.manifest)
            self.assertEqual(state["phase"], "exploit-triggering")
            self.assertIn("stock_wifi_restore", state)
            self.assertEqual(os.stat(self.manifest).st_mode & 0o777, 0o600)
        with patch.object(install.chain, "plant"), \
             patch.object(install.chain, "trigger", side_effect=inspect) as trigger, \
             patch.object(install, "pivot") as pivot:
            self.assertEqual(install.main([
                "--network-backend", "ish", "--ish-stock-ipv6", "fe80::1234%24",
                "--stage", "preflight", "--outdir", self.root, "--settle", "0",
                "--wifi-ssid", "PhoneNet", "--wifi-key", "test-passphrase", "--wifi-country", "CN"]), 0)
        trigger.assert_called_once()
        pivot.assert_not_called()
        state = install.load_resume_manifest(self.manifest)
        self.assertEqual(state["network_backend"], "ish")
        self.assertEqual(state["phase"], "preflight-complete")

    def test_interrupted_trigger_is_not_replayed(self):
        self.resume("exploit-triggering")
        self.preflight_patches()
        with patch.object(install, "require_wifi_firstboot"), \
             patch.object(install.chain, "plant") as plant, \
             patch.object(install.chain, "trigger") as trigger:
            self.assertEqual(install.main(["--resume-manifest", self.manifest,
                                           "--stage", "preflight", "--settle", "0"]), 0)
        plant.assert_not_called()
        trigger.assert_not_called()

    def test_different_stock_device_stops_before_exploit(self):
        server = self.preflight_patches()
        with patch.object(net, "read_stock_identity6", return_value=dict(self.identity, id="other-device")), \
             patch.object(install.chain, "plant") as plant:
            with self.assertRaises(net.NetworkCheckError):
                install.main(["--network-backend", "ish", "--ish-stock-ipv6", "fe80::1234%24",
                              "--stage", "preflight", "--outdir", self.root,
                              "--wifi-ssid", "PhoneNet", "--wifi-key", "test-passphrase", "--wifi-country", "CN"])
        plant.assert_not_called()
        server.assert_not_called()

    def test_flash_to_permanent_verification_with_ish_backend(self):
        """Execute the real coordinator; remote SSH/SCP are device models."""
        self.resume("pivot-complete")
        backend = ish_backend.ISHBackend(arguments(ish_permanent_address="fe80::200"),
                                          devices.RD03V2, log=lambda _: None,
                                          resume={"ish_art_sha256": "b"*64, "ish_art_size": 1048576})
        state = {"upgraded": False}
        mtd = '\n'.join(f'mtd{i}: {size:08x} 00020000 "{name}"'
                        for i, (name, (_, size)) in enumerate(devices.RD03V2.openwrt_partitions.items()))
        mtd += '\nmtd2: 00100000 00020000 "0:art"'
        def ssh(host, command, **kwargs):
            if command == "echo up":
                return 0, "up"
            if command.endswith("board_name"):
                return 0, devices.RD03V2.openwrt_board
            if command.endswith("rootfs_type"):
                return 0, "overlay" if state["upgraded"] else "tmpfs"
            if command == "cat /proc/mtd":
                return 0, mtd
            if "fw_printenv" in command:
                return 0, "11"
            if command == "sha256sum /tmp/fw.bin":
                return 0, "a"*64 + "  /tmp/fw.bin"
            if command == "sha256sum /dev/mtd2":
                return 0, "b"*64 + "  /dev/mtd2"
            if "pgrep" in command:
                return 1, ""
            if "start-stop-daemon" in command:
                return 0, "rc=0 status=started"
            if "touch /tmp/xiaomi-sysupgrade.ack" in command:
                self.assertEqual(install.load_resume_manifest(self.manifest)["phase"], "flash-started")
                state["upgraded"] = True
                return 0, "ack-sent"
            return 0, ""
        with patch.object(install, "ssh", side_effect=ssh), \
             patch.object(install, "ssh_banner", return_value=("SSH-2.0-dropbear_2024.86", None)), \
             patch.object(install, "scp_to") as scp, \
             patch.object(install, "confirm"), \
             patch.object(install, "require_permanent_nand_support", return_value=("11", "part", "model gate")), \
             patch.object(install.time, "sleep"), \
             patch.object(net, "discover_unicast", return_value="fe80::200%11") as discover, \
             patch.object(install, "default_gateways", side_effect=AssertionError("Linux route lookup")):
            install.flash("fe80::100%24", self.rel, self.images, False, devices.RD03V2, self.root,
                          manifest_path=self.manifest, transport="wifi", verify_interface="ish-wifi",
                          permanent_wifi_ssid="PhoneNet", verify_transport="wifi", network=backend)
        self.assertEqual(install.load_resume_manifest(self.manifest)["phase"], "flash-complete")
        self.assertEqual(backend.phase, "permanent")
        self.assertEqual(discover.call_args.args[0], "fe80::200")
        self.assertTrue(all(call.kwargs["network"] is backend for call in scp.call_args_list))


if __name__ == "__main__":
    unittest.main()
