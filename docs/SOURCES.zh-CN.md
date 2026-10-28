# 软件来源和许可证说明

[返回首页](../README.md) · [文件与版本](ARTIFACTS.zh-CN.md)

本项目已作为独立仓库维护，提供 iPhone 刷机适配、中文教程、问题处理记录和下载文件。独立维护改变的是仓库关系，不代表所用的软件都由本项目从零编写。这里集中列出来源，方便检查代码、版本和许可证。

## 手机刷机工具

基础代码来自 [ADCDS/xiaomi-openwrt-install](https://github.com/ADCDS/xiaomi-openwrt-install)，本仓库使用的基础提交是：

```text
2ca24a165a54f11af98cdea1ba8f4fef69c97ec1
```

本项目增加了 iPhone iSH 网络适配、换 Wi-Fi 后重新连接、安装进度保存与结果检查，以及配套测试和中文教程。这些改动尚未合入基础项目。本次整理文档没有改变原有刷写逻辑。

[LICENSE](../LICENSE) 和 [NOTICE](../NOTICE) 保留。NOTICE 也说明了安装器使用的原厂漏洞、操作影响和风险。相关技术公开记录见 [xiaomi-ax3000t-cabmeshd-disclosure](https://github.com/ADCDS/xiaomi-ax3000t-cabmeshd-disclosure)。

基础项目的软件检查记录是 259 通过、0 失败、1 跳过；本仓库适配测试为 50 项通过。实际手机操作和未验证部分另见[实际使用记录](HARDWARE-VALIDATION.zh-CN.md)，不能把不同环境的测试混为一谈。

## 固件

固件来自 [ADCDS/openwrt-xiaomi-ax3000t-rd03v2](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2)，本次使用 v2.0.2。下载页保存的是原始文件，未重新打包、改签名或加入个人节点。

- [v2.0.2 固定源码版本](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2/tree/v2.0.2)
- [该版本的构建说明](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2/blob/v2.0.2/docs/building.md)
- [基础源码版本记录](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2/blob/v2.0.2/upstream.lock)
- [配套软件源版本记录](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2/blob/v2.0.2/feeds.lock)
- [基础源码保存仓库](https://github.com/ADCDS/openwrt)及 [NSS 软件源码仓库](https://github.com/ADCDS/nss-packages)

固件包含多种软件，各自的许可证不因本仓库独立维护而改变。本仓库的安装器许可证不能代替固件中所有组件的许可证。

## OpenClash 和 Mihomo

- 插件来自 [vernesong/OpenClash](https://github.com/vernesong/OpenClash)，本次使用 v0.48.002。
- 实际处理连接的程序是 [MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo)，本次使用 `alpha-gbc76c13`，程序从 OpenClash 官方 core 分支取得。
- 为降低安装时内存占用，本次在另一台机器用 [UPX](https://github.com/upx/upx) 5.2.1 去掉程序的压缩包装，没有修改其配置或加入账号。本仓库没有重新分发 Mihomo 和 UPX 二进制。

## dnsmasq 补丁

这个包是针对本次 v2.0.2 环境单独编译的，源码来自 [kuncy7/openwrt-nss-edma](https://github.com/kuncy7/openwrt-nss-edma) 的 `ipq50xx-2026.10.19` 标签。对应的完整 dnsmasq 源码、配方、补丁、构建配置和说明与 APK 一起发布，详见[文件与版本说明](ARTIFACTS.zh-CN.md)。

这是本项目提供的单独编译包，不是固件作者签名的官方安装包。按教程核对文件后再使用，不全局关闭系统签名检查。

## 保留的技术来源

用于生成候选网络地址的设备描述来自这个[固定版本源码](https://github.com/ADCDS/openwrt/blob/900aedbd99676c884b09d3138ddc98cf7cd839d0/target/linux/qualcommax/dts/ipq5018-mi-router-ax3000t-v2.dts)：该版本使用 ART 偏移 6 处的数据设置 LAN MAC。工具仍会验证实际设备，不假定所有以后版本的网络地址都一样。

仓库里的下载地址、版本记录、源码署名和许可证用于保证来源清楚、功能可用。删除 GitHub 的 Fork 关系后，这些内容仍有保留的用途。
