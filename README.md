# AX3000T RD03v2 iPhone iSH client

实验性的 iPhone iSH 安装客户端，基于
[ADCDS/xiaomi-openwrt-install](https://github.com/ADCDS/xiaomi-openwrt-install)
提交 `2ca24a165a54f11af98cdea1ba8f4fef69c97ec1`。

已接入 iSH 的 socket 网络后端和断线续接，保留板型、分区、NAND、备份与镜像校验。
**尚未在 iPhone 上完成从原厂到 OpenWrt 的端到端刷写，当前只进行只读预检。**

请先阅读 [中文 iSH 使用与验证说明](README-ISH.zh-CN.md)。
下载客户端请到 [Releases](https://github.com/zwthys-cyber/ax3000t-ish-client/releases)。
发布附件是客户端源码验证包，不包含固件。

## 当前可执行的手机步骤

在 iSH 前台安装依赖：

```sh
apk add python3 openssh-client sshpass openssl ca-certificates curl unzip
```

下载并解压 release 客户端后，先运行以下只读预检。将示例地址替换为手机实际验证的
原厂路由器 IPv6 link-local 地址与数字接口编号：

```sh
python3 ish_preflight.py --runtime --stock-ipv6 'fe80::1%24'
```

该预检只读取路由器信息，并在手机创建、测试、清除临时状态文件。
`flash_ready: false` 是预期输出，预检通过不等于刷写验证通过。
`install.py --stage preflight` 会取得 root 并修改原厂配置，不能用作只读检测。

## 软件验证

- 41 项适配和中断恢复测试通过；在 Alpine 3.14 x86 / Python 3.9.16 / OpenSSH 8.6p1 上也通过。
- 上游 selftest：259 通过、0 失败、1 跳过（缺少原厂镜像输入）。
- 同一旧版 Alpine 环境完成了 iSH 模式真实 dry-run，下载并校验 v2.0.2 的三个镜像及 UBI/ITB 对应关系；未接触路由器。

详情见 [ISH_VALIDATION.json](ISH_VALIDATION.json)。Alpine chroot 测试不等于 iOS 或 iSH 实机测试。

```sh
python3 -m unittest -q test_ish_network test_ish_backend
```

[上游 README](README.upstream.md)、[NOTICE](NOTICE) 与 [GPL-2.0 许可证](LICENSE) 保留。
原厂恢复脚本 revert.py / restore.py 未适配 iSH。
