# 本次版本、附件与可复现来源

[返回首页](../README.md) · [本次附件发布](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/rd03v2-guide-20261028)

## 实机版本

| 项目 | 本次值 |
| --- | --- |
| 设备 | Xiaomi Mi Router AX3000T v2 / RD03v2 / IPQ5018 |
| NAND | ESMT F50D1G41LB，`flash_type=0x11` |
| 固件发行 | ADCDS v2.0.2 |
| OpenWrt | SNAPSHOT `r0+37778-bc808b8504` |
| target / 用户态架构 | `qualcommax/ipq50xx` / `aarch64_cortex-a53` |
| kernel 包 | `6.18.55~0291e1f42381ec93b4f2f7e33bbdb41a-r1` |
| OpenClash | `v0.48.002` |
| 本次 Mihomo | `alpha-gbc76c13`，linux arm64，Go 1.26.9 |

型号、NAND、kernel ABI 和用户态库版本都参与兼容性判断；这个表不是其他机器的通用安装保证。

## 固件原版镜像

本次使用的 v2.0.2 上游原始镜像、配套软件包、支持表、构建元数据和 SHA-256 已另行收录到[固件发布页](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/firmware-v2.0.2-upstream-mirror)，文件名、签名与上游摘要保持不变。该发布包含中文文件用途与固定源码链接；不是预装 OpenClash 的自定义固件。安装器仍使用上游发行元数据及校验逻辑，本次没有改动下载或刷写代码。

## 自编译 dnsmasq 补丁附件

Release 包含 `dnsmasq-full-2.93-r4-rd03v2-nftset.apk`、`RD03v2-dnsmasq-nftset-source.tar.gz`、`RD03v2-dnsmasq-build-notes.md` 与 `SHA256SUMS`。

APK SHA-256：

```text
0d1594f6978375aae46892f6b18a85b730343e4808ad69a125af0227be2a9782
```

这是独立构建的用户态包，非 ADCDS / OpenWrt 官方签名包。适用本文 v2.0.2 库环境，提供 `dnsmasq=2.93-r4` 满足原系统 world 固定约束，在一次依赖解析事务中替换原包。依赖为 libc、libnettle8、libubus20260925、nftables-json；不依赖缺失的 conntrack netlink kmod。

源码来自 [kuncy7/openwrt-nss-edma](https://github.com/kuncy7/openwrt-nss-edma) 的 `ipq50xx-2026.10.19` 标签中 `package/network/services/dnsmasq`，上游 dnsmasq 2.93 源码 SHA-256 为 `0c00d4e5c97c8306e5fb932b348b34269c9c29a0e7df0e8e82958b407092bc19`。源代码归档包含完整上游源码压缩包、配方、补丁、构建配置及构建时验证记录，保留各自的许可文件。

构建使用 OpenWrt qualcommax/ipq50xx gcc-14.4.0 musl SDK；SDK 摘要为 `600bbbab43b322a34663fe4189e04b5895d2247db4449e9e652ea20663e38910`，base feed 固定 `6b7ea6896a3a83c9ae80d31e8d35d911e032268f`。复现步骤见附件构建说明。源码归档里的 README 是构建当时状态，后续路由器验证见[实机记录](HARDWARE-VALIDATION.zh-CN.md)，不修改原构建附件来伪造新结果。

## 官方 OpenClash APK

来源：[v0.48.002 Release](https://github.com/vernesong/OpenClash/releases/tag/v0.48.002)。

文件 `luci-app-openclash-0.48.002.apk` 的 SHA-256：

```text
f7ebbd43f9be15c5e6df26e5d0c03d50d0bb8f7fa4cc0d2c2bf048b08c0b155b
```

## ucode / RPC 兼容修复记录

旧 ucode 为 `2026.07.09~b885dd0f-r1`，本次定向升级到 `2026.10.23~aabdeb4f-r1`，对应 LuCI base `26.297.60563~4bfd110`。本次重新安装的官方重建 RPC 包：

```text
https://downloads.openwrt.org/snapshots/packages/aarch64_cortex-a53/base/rpcd-mod-ucode-2026.10.04~d99f703e-r1.apk
SHA256: 0c188e2b8b1c54cdf98415278e330c588c6ba101a0e162550761791fe123ead1
```

SNAPSHOT 地址可能移除旧文件；即使同名，也必须核对库依赖与摘要，不要用强制选项把 ABI 错误掩盖掉。本文不将滚动源当作永久归档。

## Mihomo 解包说明

本次从 [OpenClash 官方 core 分支](https://github.com/vernesong/OpenClash/tree/core/master/meta)取得 ARM64 tar.gz，用 UPX 5.2.1 解包 ELF，没有重新编译、修改配置或注入凭据。

解包后 SHA-256：

```text
498d4eb798489e725fb11514461d33011bd24957185da0f45cb7647144ffd11d
```

模拟环境中最小配置测试通过；QEMU 下 `-v` maxRSS 从 87,704 KiB 降为 62,088 KiB，这是宿主模拟器测量，不等于路由器 RSS。实机直接传入解包 ELF 后版本检查成功，后续服务约 24 MiB RSS。保留官方 [Mihomo 源码](https://github.com/MetaCubeX/mihomo)与 [UPX 源码](https://github.com/upx/upx)入口，本仓库不重新分发这两个工具的二进制。
