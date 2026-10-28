# 小米 AX3000T RD03v2：iPhone 刷 OpenWrt 与 OpenClash 中文实战

使用 iPhone 上的 iSH 完成原厂系统 → RAM 安装系统 → NAND 永久安装，再配置中文 LuCI 和 OpenClash。本仓库保留 iSH 安装客户端，并整合 2026-10-28 这台设备的完整操作与排错记录。

**本次已在一台 RD03v2 实机完成 NAND 安装，校验得到 `rootfs_type=overlay`；OpenClash 已运行，DNS 排错后用户确认访问明显变快。** 这是单台设备记录，不代表所有硬件、版本或 iOS 中断情形都已验证。

默认使用 **`main` 分支**：本仓库的 iPhone iSH 适配和下列中文教程均在这个分支。固件请到 Releases 下载，不按分支选择固件。

## 从这里开始

| 需要做什么 | 文档 |
| --- | --- |
| 从原厂刷机、换 Wi-Fi、断线后验证 | [完整中文实战教程](docs/GUIDE.zh-CN.md) |
| 安装 OpenClash、处理依赖和低内存 | [OpenClash 安装与排错](docs/OPENCLASH.zh-CN.md) |
| 查询本次版本、补丁包来源和哈希 | [版本与补丁包](docs/ARTIFACTS.zh-CN.md) |
| 理解 iSH 的网络、续接与验证边界 | [iSH 使用与验证说明](README-ISH.zh-CN.md) |
| 选分支/下载、密码、备份与常见问题 | [常见问题速查](docs/FAQ.zh-CN.md) |
| 配置结构参考（需要填自己的节点参数） | [Mihomo 示例](examples/mihomo.example.yaml) |
| 查看这次仓库更新 | [更新记录](docs/CHANGELOG.zh-CN.md) |
| 看脱敏的实机结果 | [实机验证记录](docs/HARDWARE-VALIDATION.zh-CN.md) |
| 下载本次使用的 v2.0.2 原版固件 | [固件下载镜像](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/firmware-v2.0.2-upstream-mirror) |
| 下载客户端与本次 dnsmasq 补丁附件 | [Releases](https://github.com/zwthys-cyber/ax3000t-ish-client/releases) |

## 适用设备与来源

- **小米 AX3000T RD03v2，高通 IPQ5018，`qualcommax/ipq50xx`**。本次 NAND 为 ESMT F50D1G41LB，`flash_type=0x11`。
- 固件：[ADCDS/openwrt-xiaomi-ax3000t-rd03v2](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2)，本次使用 **v2.0.2**。
- 安装工具基于 [ADCDS/xiaomi-openwrt-install](https://github.com/ADCDS/xiaomi-openwrt-install)，固定基础提交 `2ca24a165a54f11af98cdea1ba8f4fef69c97ec1`，增加 iSH 网络后端、续接与验证。
- OpenClash：[vernesong/OpenClash](https://github.com/vernesong/OpenClash)，本次插件 **v0.48.002**。

这里是客户端和教程仓库，不是新的固件发行版。旧版联发科 RD03/RD23 的镜像不能用于这台高通 RD03v2。实际刷写会改写 NAND；先阅读 [NOTICE](NOTICE)，备份留在自己手中，不能跳过安装器的板型、NAND、ART 和镜像校验。

## 软件验证

历史验证：50 项适配与中断恢复测试通过；上游 selftest 259 通过、0 失败、1 跳过。Alpine 3.14 x86 / Python 3.9.16 / OpenSSH 8.6p1 环境也通过适配测试。详见 [ISH_VALIDATION.json](ISH_VALIDATION.json)。本次新增内容为文档和实机验证状态，没有改动刷写逻辑。

```sh
python3 -m unittest -q test_download_resume test_ish_network test_ish_backend
```

上游 [README](README.upstream.md)、[技术说明](docs/technical.md)、[NOTICE](NOTICE) 与 [GPL-2.0 许可证](LICENSE) 保留。`revert.py` / `restore.py` 未完成 iSH 实机验证。
