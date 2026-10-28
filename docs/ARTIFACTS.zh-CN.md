# 下载文件、所用版本和来源说明

[返回首页](../README.md) · [常见问题](FAQ.zh-CN.md) · [工具和补丁下载](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/rd03v2-guide-20261028)

## 这次用的是什么版本

| 项目 | 本次值 |
| --- | --- |
| 设备 | Xiaomi Mi Router AX3000T v2 / RD03v2 / IPQ5018 |
| 闪存芯片（NAND） | ESMT F50D1G41LB，`flash_type=0x11` |
| 固件版本 | ADCDS v2.0.2 |
| OpenWrt | SNAPSHOT `r0+37778-bc808b8504` |
| 系统平台 / 安装包架构 | `qualcommax/ipq50xx` / `aarch64_cortex-a53` |
| 系统内核版本（完整编号） | `6.18.55~0291e1f42381ec93b4f2f7e33bbdb41a-r1` |
| OpenClash | `v0.48.002` |
| 本次 Mihomo | `alpha-gbc76c13`，linux arm64，Go 1.26.9 |

安装包能不能用，要同时看路由器型号、闪存芯片、系统内核和相关软件版本。不要只看文件名相似就安装；上表记录的是这次设备的情况。

## 固件：路由器要安装的系统

[固件下载页](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/firmware-v2.0.2-upstream-mirror)保存了原作者 v2.0.2 的固件和配套文件，内容、文件名、签名和校验值都与原版一致。

下载页附有中文文件用途说明。固件没有预装 OpenClash；后面按教程单独安装。手机刷机工具仍按原作者提供的信息下载和检查文件，这次没有修改刷写程序。

## 客户端 ZIP：在 iPhone 上运行的刷机工具

下载 `ax3000t-ish-client.zip` 后，解压会得到 `ax3000t-ish-client/` 文件夹，里面有刷机程序、中文教程和没有填真实账号的配置示例。它不含固件、设备备份或可用节点。

`CLIENT-SNAPSHOT.txt` 说明这个 ZIP 对应哪次代码更新；`SHA256SUMS` 记录它和补丁文件的完整性校验值。旧 v0.1.x 下载页保留当时说明，要看更新后的教程请用本次下载包或默认分支。

## dnsmasq 补丁：解决本次安装遇到的缺包问题

Release 包含 `dnsmasq-full-2.93-r4-rd03v2-nftset.apk`、`RD03v2-dnsmasq-nftset-source.tar.gz`、`RD03v2-dnsmasq-build-notes.md` 与 `SHA256SUMS`。

下面是这个安装包的 SHA-256。按教程下载后，检查结果必须一致：

```text
0d1594f6978375aae46892f6b18a85b730343e4808ad69a125af0227be2a9782
```

这个补丁是为本次系统单独编译的，不是 ADCDS 或 OpenWrt 官方签名包。它仍提供系统要求的 `dnsmasq=2.93-r4`，让安装程序在一次操作中替换旧包，不需要先强行删除原程序。

适用的是本文 v2.0.2 的软件环境。所需配套软件为 libc、libnettle8、libubus20260925、nftables-json，不需要本次下载服务器缺少的 conntrack netlink 内核模块。

### 给想自己编译或核对来源的人

普通用户可以按安装教程使用已提供的包；下面保留源码、编译环境和校验信息，方便进一步核对。

源码来自 [kuncy7/openwrt-nss-edma](https://github.com/kuncy7/openwrt-nss-edma) 的 `ipq50xx-2026.10.19` 标签中 `package/network/services/dnsmasq`，上游 dnsmasq 2.93 源码 SHA-256 为 `0c00d4e5c97c8306e5fb932b348b34269c9c29a0e7df0e8e82958b407092bc19`。源代码归档包含完整上游源码压缩包、配方、补丁、构建配置及构建时验证记录，保留各自的许可文件。

构建使用 OpenWrt qualcommax/ipq50xx gcc-14.4.0 musl SDK；SDK 摘要为 `600bbbab43b322a34663fe4189e04b5895d2247db4449e9e652ea20663e38910`，base feed 固定 `6b7ea6896a3a83c9ae80d31e8d35d911e032268f`。复现步骤见附件构建说明。源码归档里的 README 是构建当时状态，后续路由器验证见[实机记录](HARDWARE-VALIDATION.zh-CN.md)，不修改原构建附件来伪造新结果。

## OpenClash APK：插件安装包

来源：[v0.48.002 Release](https://github.com/vernesong/OpenClash/releases/tag/v0.48.002)。

文件 `luci-app-openclash-0.48.002.apk` 的 SHA-256：

```text
f7ebbd43f9be15c5e6df26e5d0c03d50d0bb8f7fa4cc0d2c2bf048b08c0b155b
```

## 网页打不开时用到的配套组件

旧 ucode 为 `2026.07.09~b885dd0f-r1`，本次定向升级到 `2026.10.23~aabdeb4f-r1`，对应 LuCI base `26.297.60563~4bfd110`。本次重新安装的官方重建 RPC 包：

```text
https://downloads.openwrt.org/snapshots/packages/aarch64_cortex-a53/base/rpcd-mod-ucode-2026.10.04~d99f703e-r1.apk
SHA256: 0c188e2b8b1c54cdf98415278e330c588c6ba101a0e162550761791fe123ead1
```

这些是本次修复时用过的确切文件。SNAPSHOT 下载服务器可能删除旧文件；以后再下载，即使文件名相同，也要检查版本、配套软件和校验值。不要强制忽略错误继续安装。

## Mihomo：OpenClash 实际处理连接的程序

本次从 [OpenClash 的官方程序下载位置](https://github.com/vernesong/OpenClash/tree/core/master/meta)取得 ARM64 程序，在另一台机器上用 UPX 5.2.1 去掉压缩包装。程序没有重新编译，也没有加进配置或账号。操作原因和步骤见 [OpenClash 教程](OPENCLASH.zh-CN.md)。

解包后 SHA-256：

```text
498d4eb798489e725fb11514461d33011bd24957185da0f45cb7647144ffd11d
```

模拟环境中最小配置测试通过；QEMU 下 `-v` maxRSS 从 87,704 KiB 降为 62,088 KiB，这是宿主模拟器测量，不等于路由器 RSS。实机直接传入解包 ELF 后版本检查成功，后续服务约 24 MiB RSS。保留官方 [Mihomo 源码](https://github.com/MetaCubeX/mihomo)与 [UPX 源码](https://github.com/upx/upx)入口，本仓库不重新分发这两个工具的二进制。
