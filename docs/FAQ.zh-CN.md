# 下载、备份与常见问题速查

[返回首页](../README.md) · [完整刷机教程](GUIDE.zh-CN.md) · [OpenClash 排错](OPENCLASH.zh-CN.md)

## 分支和下载

**用哪个分支？** 使用默认且唯一的 `main`。iPhone iSH 适配、客户端和中文教程均已整合在这里，提交历史完整保留。

**下载哪个 Release？**

| 需要的内容 | 入口 |
| --- | --- |
| 本次使用的 v2.0.2 固件、配套包与上游校验文件 | [固件原版镜像](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/firmware-v2.0.2-upstream-mirror) |
| 更新后的中文教程和 iSH 客户端压缩包 `ax3000t-ish-client.zip` | [教程与客户端](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/rd03v2-guide-20261028) |
| 自编译 dnsmasq-full APK、完整对应源码和构建说明 | [同一教程发布的附件](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/rd03v2-guide-20261028) |

**只用 iPhone，怎么获取客户端？** 把 `ax3000t-ish-client.zip` 下载到“文件”App 的 iSH → root。首次解压：

```sh
cd /root
unzip ax3000t-ish-client.zip
cd /root/ax3000t-ish-client
```

已开始安装的用户不要解压覆盖原安装目录；原目录的 `resume.json`、备份和 firstboot 归档必须保留。更新客户端时先备份旧目录，在另一目录检查新版本，不启动第二次安装。

**下载 Source code.zip 可以吗？** GitHub 自动生成的 Source code 是本仓库安装器与教程，**不是固件**。固件文件在发布页 Assets 的 `.ubi`、`.itb`、`.bin` 附件中；先按[刷机教程](GUIDE.zh-CN.md)确认各自用途。

**镜像自带 OpenClash 吗？** 不带。镜像是 ADCDS v2.0.2 原始文件，中文包、OpenClash、dnsmasq 补丁和私人节点配置是安装后的操作。教程没有把设备备份当作“固件”公开。

**只刷一个 sysupgrade.bin 就行吗？** 原厂首次安装不是这样：先用安装器取得 root 和备份，写空闲槽，进入 RAM 安装系统，验证设备身份，再执行 sysupgrade。已安装 OpenWrt 的后续升级也遵循[上游该版本 RAM 升级说明](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2/blob/v2.0.2/docs/no-uart-reflash.md)，不从普通运行系统盲目强刷。

## 密码与 Wi-Fi

**提示输入 root password，要填什么？** 是首次配置的路由器 root 登录密码；不是永久 Wi-Fi 密码，也不是 RAM 安装网络的固定密钥。终端不回显字符是正常现象。

**Wi-Fi 为什么有两项同名？** LuCI 分别显示 2.4 GHz 和 5 GHz，iPhone 通常把同名、同认证的网络合并显示。已连接站点会显示实际 radio；本次连在 5 GHz。

**Wi-Fi 密码 6 位可以吗？** 本安装器使用 WPA2，要求 8～63 个可打印 ASCII 字符。root 密码长度与这个限制不是同一个概念。

**为什么管理页面换成 192.168.10.1？** 本次 WAN 在 `192.168.1.0/24`，LAN 原来也是同一网段，故将 LAN 改到 `192.168.10.0/24`。不要不看上游网段就照改；改 LAN 后需要手机重新获取地址。

## 实际排错

| 现象 | 先检查 |
| --- | --- |
| `apk update` 下载失败 | WAN 网线、Carrier、DHCP 地址、上下游网段、DNS，再查看具体源错误 |
| 安装结束后 SSH Permission denied | 是否连接永久 Wi-Fi、是否用了最初设置的 root 密码；用 `--verify-only` 校验，不重刷 |
| `client_loop ... Broken pipe` | SSH 已退出；提示符回到 `localhost` 后重新 SSH，不在手机环境跑路由器诊断 |
| OpenClash 菜单不存在 / 404 | 控制器文件、Lua 桥接和 ucode ABI；不能只反复清缓存 |
| `luci/getFeatures ... Object not found` | rpcd-mod-ucode 是否与已升级的 ucode 库匹配 |
| Meta 下载成功但更新失败 | 路由器 dmesg 是否有 OOM；不要反复同时点更新 |
| 站点能打开但每次等约 5 秒 | 检查真实 DNS 路径、全局 DNS 遵循规则覆盖及日志，不只看节点测速 |
| `/tmp` 很空但仍内存不足 | `/tmp` 属于 RAM，执行、解压和下载会叠加占用；同时看可用内存与 OOM 日志 |

## 备份与分享

安装器备份与 OpenWrt 配置备份不是一回事：

- 安装前/过程中生成的 ART、APPSBLENV、bdata、APPSBL、nvram、resume 和 firstboot 归档用于原设备诊断与恢复，保存在私有存储，不能公开。
- 安装完成后可用 LuCI“系统 → 备份/升级 → 生成备份”下载当前设置。先检查备份清单：第三方插件文件和大内核不一定在默认备份里，配置备份也不等于完整 flash 镜像。
- 单独私下保存自己的 OpenClash 配置/订阅和需要的插件设置，记录对应版本；不要把真实配置填进公开示例。
- 电脑或其他可访问路由器的可信设备可以用 SCP 接收文件；仅有 iPhone 时优先使用 LuCI 下载与 iSH 文件导出。保存后检查文件存在、大小合理，关键文件保留 SHA-256。

仓库增加了常见私有运行产物的 `.gitignore` 规则，但它无法撤销已经提交的秘密。提交前检查 `git status` 和 `git diff --cached`；分享诊断输出时只保留必要错误，不分享真实密码或完整续接记录。
