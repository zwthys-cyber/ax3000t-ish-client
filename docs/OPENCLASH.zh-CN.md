# RD03v2 v2.0.2：OpenClash 安装、低内存与 DNS 排错

[返回首页](../README.md) · [刷机与联网](GUIDE.zh-CN.md) · [附件、源码与哈希](ARTIFACTS.zh-CN.md)

本文是 OpenWrt SNAPSHOT `r0+37778-bc808b8504`、内核 `6.18.55`、OpenClash `0.48.002` 的实测记录。SNAPSHOT 软件源会变化，不能保证未来的最新包仍与旧固件兼容。**不要执行全系统 `apk upgrade`，也不要强制绕过内核依赖。**

## 1. 先确认登录的是路由器

在手机 iSH：

```sh
ssh root@192.168.10.1
```

初次连接核对主机指纹后输入 `yes`，再输入路由器 root 密码。只有看到 `root@OpenWrt:~#` 才执行下文命令。`Broken pipe` 表示 SSH 已断开；回到 `localhost` 后要重新 SSH。

先确认网络和资源：

```sh
nslookup downloads.openwrt.org 127.0.0.1
df -h /overlay /tmp
free
```

本次系统可见总内存约 170.7 MiB，安装前可用约 35 MiB；overlay 约 58.6 MiB。`/tmp` 是内存文件系统，显示有空间不代表能同时容纳下载、解压和内核运行。`free` 的数字需按实际输出单位判断，不能因为输入了 `-m` 就把所有数字当 MiB。

## 2. 安装依赖，先模拟再安装

本次以下命令先模拟通过，再执行安装：

```sh
apk add --simulate bash curl ca-bundle ip-full ruby ruby-yaml \
  kmod-tun kmod-inet-diag unzip kmod-nft-tproxy luci-compat luci luci-base
```

确认没有缺包、kernel ABI 冲突或意外删除后，去掉 `--simulate`：

```sh
apk add bash curl ca-bundle ip-full ruby ruby-yaml \
  kmod-tun kmod-inet-diag unzip kmod-nft-tproxy luci-compat luci luci-base
```

这只证明本次源状态能解析依赖。未来源若不匹配，应使用固件维护者提供的匹配包或匹配 SDK 重建，不能仅凭 `6.18.55` 数字相同认定所有 kmod 兼容。

## 3. dnsmasq-full 冲突如何处理

本次直接安装源里的 `dnsmasq-full` 失败：原系统固定 `dnsmasq=2.93-r4`，滚动源已经是 `2.93-r6`；其依赖 `libnetfilter-conntrack3` 又要求源中不存在的 `kmod-nf-conntrack-netlink`。

检查：

```sh
apk policy dnsmasq dnsmasq-full libnetfilter-conntrack3
apk search '*conntrack*'
dnsmasq --version
apk info -a kernel
```

原版显示 `no-nftset`。本次为 **v2.0.2 / aarch64_cortex-a53** 构建了保留原补丁 init 的 `dnsmasq-full 2.93-r4`：启用 nftset、DHCPv6、DNSSEC，关闭本例未使用的 conntrack 与 ipset。这样无需伪造或强装缺失 kmod。源码、构建配置和 APK 在[本次附件发布](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/rd03v2-guide-20261028)。

确认自己版本与[适用范围](ARTIFACTS.zh-CN.md)匹配，再下载并验证：

```sh
curl -fL --connect-timeout 15 --max-time 180 \
  'https://github.com/zwthys-cyber/ax3000t-ish-client/releases/download/rd03v2-guide-20261028/dnsmasq-full-2.93-r4-rd03v2-nftset.apk' \
  -o /tmp/dnsmasq-full.apk
echo '0d1594f6978375aae46892f6b18a85b730343e4808ad69a125af0227be2a9782  /tmp/dnsmasq-full.apk' | sha256sum -c -
```

只有输出 `OK` 才继续。先保留 DHCP 配置，再模拟：

```sh
cp -p /etc/config/dhcp /root/dhcp-before-openclash.conf
apk add --simulate --allow-untrusted /tmp/dnsmasq-full.apk
```

本次模拟仅替换原 dnsmasq、增加 libnettle8、安装 dnsmasq-full，没有删除系统网络组件。实际执行：

```sh
apk add --allow-untrusted /tmp/dnsmasq-full.apk
dnsmasq --version
/etc/init.d/dnsmasq restart
```

`--allow-untrusted` 只用于这一个自编译包，不要全局关闭签名验证。输出中的 `no-conntrack no-ipset nftset` 是本补丁的预期特性。保留现有 `/etc/config/dhcp`；安装出现 `.apk-new` 不意味着要用它覆盖现有 LAN 设置。

重启后等几秒再验证：

```sh
/etc/init.d/dnsmasq status
nslookup downloads.openwrt.org 127.0.0.1
nslookup downloads.openwrt.org 192.168.10.1
```

本次重启后瞬间查询曾 `Connection refused`，后续查询正常。若持续失败，查看 `logread -e dnsmasq | tail -n 60` 和 `logread -e ujail | tail -n 30`，不能只凭一次 `running` 判定 DNS 可用。`udhcpc: no lease, failing` 单条信息不足以判定整个 WAN 故障，应结合接口地址和 DNS 实测。

## 4. 安装官方 OpenClash APK

```sh
curl -fL --retry 2 --connect-timeout 15 --max-time 180 \
  'https://github.com/vernesong/OpenClash/releases/download/v0.48.002/luci-app-openclash-0.48.002.apk' \
  -o /tmp/openclash.apk &&
echo 'f7ebbd43f9be15c5e6df26e5d0c03d50d0bb8f7fa4cc0d2c2bf048b08c0b155b  /tmp/openclash.apk' | sha256sum -c - &&
apk add --allow-untrusted /tmp/openclash.apk
```

安装后应出现“服务 → OpenClash”。下载和安装必须完成才刷新界面。

## 5. 没有“服务”菜单或访问 OpenClash 404

本次控制器文件存在，但 Lua 桥接无法加载：

```sh
ls -l /etc/config/openclash /usr/lib/lua/luci/controller/openclash.lua
ucode -e 'require("lua"); print("Lua bridge OK\n");'
logread -e uhttpd | tail -n 40
```

关键错误是：

```text
Error relocating /usr/lib/ucode/lua.so: ucv_metamethod_lookup: symbol not found
Lua controller ... present but no Lua runtime installed.
```

原因是旧固件 `ucode 2026.07.09` 与后来安装的 `ucode-mod-lua 2026.10.23` ABI 不匹配，不是简单缺一个控制器文件。仅清浏览器缓存无法修复。

本次对整组 ucode 组件进行一致版本的定向升级，先模拟检查：

```sh
apk add --simulate --upgrade \
  ucode ucode-mod-fs ucode-mod-ubus ucode-mod-uci \
  ucode-mod-uloop ucode-mod-digest ucode-mod-log \
  ucode-mod-nl80211 ucode-mod-rtnl ucode-mod-lua luci-base
```

本次模拟只升级 10 个包至匹配版本；确认你当前模拟结果也合理后，才去掉 `--simulate` 执行。完成后重新测试 Lua 桥接。

若随后 LuCI 报 `luci/getFeatures ... Object not found`，检查 `rpcd-mod-ucode` 是否仍链接旧 libucode。**本次即便包版本文字相同，也要替换成重新构建、匹配新 ABI 的包**；当时使用的确切包和哈希见 [附件说明](ARTIFACTS.zh-CN.md)。未来滚动源可能已不再提供该文件，因此这一步是版本排错记录，不能盲目下载其他固件的同名包。

在软件源当前仍提供匹配重建包的前提下，可先模拟重新安装：

```sh
apk fix --simulate --reinstall rpcd-mod-ucode
```

确认来源、依赖和版本一致后，去掉 `--simulate` 执行；重新安装是为了替换旧 ABI 文件，即使显示的版本号没有变化也有意义。若匹配包已从源中移除，应先恢复对应的软件源或从匹配源码构建，不对其他版本盲目执行。

匹配包修复后重启服务并清菜单缓存：

```sh
rm -f /tmp/luci-indexcache
/etc/init.d/rpcd restart
/etc/init.d/uhttpd restart
```

重新登录页面。仍失败先看服务日志，不反复重装 OpenClash。

## 6. Meta 内核下载成功但安装失败：本次是 OOM

本次内核下载 100%、校验成功，却提示 `Core Update Failed`。路由器诊断：

```sh
tail -n 40 /tmp/openclash.log
dmesg | grep -iE 'out of memory|oom|killed process' | tail -n 15
df -h /overlay /tmp
free
```

日志明确显示 `Out of memory: Killed process ... (clash_meta.new.)`。不是下载源无效，也不是换协议能解决。反复点更新会继续耗内存。

本次解决办法是在**外部电脑/服务器**把官方 ARM64 内核的 UPX 包装解开，再直接传到路由器持久存储，避免路由器执行压缩版本时的额外内存峰值。不能在本就缺内存的路由器上做解包。

来源为 OpenClash 官方 core 分支 `meta/clash-linux-arm64.tar.gz`。本次版本是 `alpha-gbc76c13`，编译目标在界面选择 `linux-arm64(armv8)`，Smart 内核关闭。官方原始 URL 是滚动内容，后来下载的文件不保证仍是这个版本。

外部 Linux 主机上，用从 [UPX 官方发布](https://github.com/upx/upx/releases)获取并核对来源的 UPX 5.2.1 执行：

```sh
curl -fL 'https://raw.githubusercontent.com/vernesong/OpenClash/core/master/meta/clash-linux-arm64.tar.gz' -o clash-linux-arm64.tar.gz
tar -tzf clash-linux-arm64.tar.gz
```

检查归档内容后提取其中的 ELF 文件，对该文件执行 `upx -d`（实际文件名以归档为准），保存为 `clash_meta.unpacked`。如果拿到的本身就是非 UPX 文件，不要强行处理。计算 SHA-256，记录版本与来源。

本次解包后约 57.4 MB，哈希为：

```text
498d4eb798489e725fb11514461d33011bd24957185da0f45cb7647144ffd11d
```

这只对应本次文件，**不是未来下载的通用哈希**。本仓库不重新分发 Mihomo 二进制，保留[官方源码与构建项目](https://github.com/MetaCubeX/mihomo)。

在路由器先停止 OpenClash，并确认更新任务结束：

```sh
/etc/init.d/openclash stop
ps -w | grep '[o]penclash_core.sh'
mkdir -p /etc/openclash/core
df -h /overlay
```

若仍有更新任务，等待结束，不并发替换。确认空间后用外部主机 SCP 传入；新版 OpenSSH 使用 `scp -O`，8.6 使用默认 SCP：

```sh
scp -O clash_meta.unpacked root@192.168.10.1:/etc/openclash/core/clash_meta.unpacked
```

设备不在同一网络时，通过自己的私有传输渠道传入并核对哈希。本次临时下载隧道已关闭，不作为公开安装入口。

然后在**路由器**核对发送端的摘要，确认无误才执行：

```sh
sha256sum /etc/openclash/core/clash_meta.unpacked
chmod 755 /etc/openclash/core/clash_meta.unpacked
mv /etc/openclash/core/clash_meta.unpacked /etc/openclash/core/clash_meta
GOMEMLIMIT=24MiB GOGC=20 /etc/openclash/core/clash_meta -v
```

本次输出正确 Mihomo 版本。这里的 Go 环境变量**只作用于这一条 `-v` 检查，不代表 OpenClash 服务已持久设置内存上限，也不是进程硬性内存限制**。本次服务实际运行 RSS 约 24 MiB，但配置规则、连接与数据库都会影响占用。避免后续自动更新把已解包文件换回压缩内核；需要更新时重新核对来源、空间及运行结果。

## 7. 导入自己的 Mihomo 配置

在 OpenClash“添加配置”或“配置管理”上传 `.yaml`，例如 `hk.yaml`。本次配置由自己的 sing-box VPS 面板导出，包含 VLESS Reality、VMess、Hysteria2、TUIC、AnyTLS；必须使用 **Mihomo/Clash 格式**，不能把 sing-box JSON 直接上传。

导入前检查：

- 删除文末多出来的空规则 `-`，也删除无意义的空 `ports:` 项。
- YAML 缩进正确，规则指向的代理组和节点确实存在。
- 将配置视为密码文件：不提交真实 UUID、password、私钥、订阅地址和控制面板 secret。
- 同一 VPS 的多个协议共用一台服务器，不等于有多个出口或带宽叠加。

可用 Ruby 检查基本 YAML 语法；它不能代替 Mihomo 的语义验证：

```sh
ruby -e 'require "yaml"; YAML.load_file(ARGV[0]); puts "YAML syntax OK"' /etc/openclash/config/hk.yaml
```

本次先选“增强”运行模式、“规则”代理模式，选定配置再启动。运行状态应显示 **Meta 运行中**。进入 Metacubexd 控制面板，在选择代理组中先选一个具体节点，观察连接与延迟；排错时固定节点更便于前后比较。

## 8. 能打开但等待很久：本次修复 DNS 遵循规则

本次 YAML 原本含 `dns.respect-rules: true`，但 OpenClash 全局设置 `openclash.config.enable_respect_rules=0` 又把它覆盖为 false。境外 DoH `1.1.1.1` / `8.8.8.8` 直接访问反复约 5 秒超时；同样的 DNS 请求走现有代理只需约 0.61 秒。

这是本次定位到的原因，不表示所有慢速都来自 DNS。先检查当前值和日志：

```sh
uci -q get openclash.config.enable_respect_rules
tail -n 60 /tmp/openclash.log
```

对于本次这种配置，先备份再开启 DNS 遵循规则：

```sh
cp -p /etc/config/openclash /root/openclash-before-dns.conf
chmod 600 /root/openclash-before-dns.conf
uci set openclash.config.enable_respect_rules='1'
uci commit openclash
/etc/init.d/openclash restart
```

需要独立可达的 `proxy-server-nameserver` 给代理节点域名解析，避免启动时 DNS 与代理互相依赖。本次已有 `https://223.5.5.5/dns-query` 与 `https://doh.pub/dns-query`；实际规则还须允许相应连接走到可用路径。不能只改一个开关而不检查自己的 DNS 和代理规则。

重启会中断现有连接，也可能把代理组重新选到配置首项。本次恢复为重启前同一个 Hysteria2 节点后，才做对照：

| 测项 | 修复前 | 修复后 |
| --- | --- | --- |
| 三个 DNS 查询 | 各约 5 秒超时 | 0.51 / 0.18 / 0.17 秒成功 |
| gstatic 204 请求 | 5.62 秒 | 0.54 秒 |
| 1 MiB 下载（含建连） | 5.91 秒 | 1.79 秒 |

用户随后确认手机端“明显变快”。这些是一次环境中的对照，不是峰值带宽承诺。目标站对 curl 返回 403 的结果没有被当作浏览器或视频播放成功证据。

如要回退本节设置，用自己的备份恢复：

```sh
cp -p /root/openclash-before-dns.conf /etc/config/openclash
/etc/init.d/openclash restart
```

不要拿别人的 UCI 全量配置覆盖自己的网络或节点信息。

## 9. 结束与保存

确认普通网页、目标服务、LAN DNS 与手机实际访问都正常后，私下保存路由器配置备份。保留 ART、原厂环境、resume 等原始备份；公开发布仅保留脱敏摘要。本次诊断使用的临时远程连接、授权和密钥均已撤销，教程不提供长期公网 SSH 或控制面板暴露方案。
