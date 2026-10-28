# AX3000T RD03v2：iPhone iSH 实验适配

2026-10-28 更新：已在一台 RD03v2（ESMT F50D1G41LB，v2.0.2）上通过 iPhone iSH 完成
原厂 root 回连、备份、RAM pivot、NAND 安装与永久系统校验。

完整操作见 [中文实战教程](docs/GUIDE.zh-CN.md)，后续见 [OpenClash 安装与排错](docs/OPENCLASH.zh-CN.md)。
下文保留只读预检与适配机制说明；单台成功不等于所有中断/恢复情形已验证。

基础项目：ADCDS/xiaomi-openwrt-install，固定提交
`2ca24a165a54f11af98cdea1ba8f4fef69c97ec1`。
本仓库的 iSH 后端、只读预检、续接记录与相关测试为实验适配，尚未合入上游。
原始 LICENSE、NOTICE 保留。固件由上游 release.py 下载验证，客户端 ZIP 不包含固件镜像。
本仓库另有[固件原版镜像 Release](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/firmware-v2.0.2-upstream-mirror)，与客户端附件分开。

## 先在手机做只读预检

把压缩包存入“文件”App 的 iSH → root 目录。看不到 iSH 时在文件 App 的浏览位置中启用它：
https://github.com/ish-app/ish/wiki/View-iSH-files-in-Files-App

在 iSH 前台执行：

```sh
apk add python3 openssh-client sshpass openssl ca-certificates unzip
cd /root
unzip ax3000t-ish-client.zip
cd ax3000t-ish-client
python3 ish_preflight.py --runtime --stock-ipv6 'fe80::1%24'
```

上面使用假设的示例地址与接口编号，必须替换成自己手机当前只读检测确认的地址。
预检读原厂 init_info、比较两个地址的设备标识、测试本地监听、检查 OpenSSH 及本地状态文件
的原子保存。它只在手机创建并清除临时测试文件，不向路由器发送写入请求。
结果不输出设备标识、序列号或 Wi-Fi 密码。

`flash_ready: false` 是预期结果：预检通过不等于完成刷写验证。
如本地 fsync/权限检查失败则停止，不能忽略失败后继续刷。
预检失败应先定位原因；通过后按完整教程进入实际安装，不能跳过镜像、设备身份与 NAND 检查。
`install.py --stage preflight` 会取得 root 并修改原厂配置，不能将它当作只读预检。

## 已实现的安装协调流程

- 显式选择 `--network-backend ish`，通过原生 socket 选取并绑定 IPv4 回连源地址，
  比较 IPv4/IPv6 原厂设备标识；不调用 Linux Netlink 或网络 sysfs。
- 保留原厂板型、版本、分区、NAND、固件哈希、备份、写入回读以及 OpenWrt tmpfs 检查。
- 对收到的 ART 备份，再从原厂 root 通道读取 MD5 比较；从 ART offset 6 的 LAN MAC 形成
  EUI-64 候选地址。这是候选，不能假定安装系统一定采用同一个地址。
- 换 Wi-Fi 后通过 TCP 单播和 Dropbear banner 重新查找数字 scope；候选不通时要求从当前
  Wi-Fi 设置读取真实 IPv6 地址。原厂、RAM 和永久系统的地址分开处理，不自动混用。
- 写永久固件前、确认安装完成前，比较原厂备份记录与设备当前 ART 的 SHA-256 和分区大小。
- 旧版 OpenSSH 8.6 使用其默认 SCP 协议；8.7 及以上显式使用 `-O`。不依赖 SFTP 服务。

固定来源中，当前固件树的设备 DTS 将 ART offset 6 作为 LAN MAC：
https://github.com/ADCDS/openwrt/blob/900aedbd99676c884b09d3138ddc98cf7cd839d0/target/linux/qualcommax/dts/ipq5018-mi-router-ax3000t-v2.dts
这不构成“所有未来固件、所有启动后的 bridge 地址都相同”的保证。

## 断线和暂停续接

整个流程不假定 iSH 能在 iOS 后台一直运行。设备上的 NAND 写入保持原有 detached 执行机制；
手机仅负责协调。手机被暂停/关闭会影响 HTTP 传输、回连和等待，不能靠“保持后台”代替续接。

每次安装目录的 resume.json 是私有续接记录，不要删除安装目录，也不要另开一个全新的安装。
它和 firstboot.tar.gz、备份一起包含敏感数据；不要上传到公开 GitHub 或发出原文。

- `exploit-triggering`：触发前先保存状态与原始 Wi-Fi 修复信息；续接只重建原 token、原回连 IP
  的监听，不再触发一次性漏洞。如果触发其实没有发生，等待会失败，不能据此重放触发。
- `preflight-complete`：原厂 root 检查已完成，可重新接通原有回连并继续备份和 RAM 阶段。
- `pivot-rebooting` / `pivot-complete`：重启前记录阶段；续接只寻找 RAM 系统并重新检查，
  不再执行原厂漏洞或 idle slot 写入。重启请求未送达时也可能停留在原厂，不能假设 RAM 已启动。
- `flash-started` / `flash-complete`：iSH 默认续接改为只读验证，绝不再次启动 sysupgrade。
  “已开始”记录写在确认设备启动标记后、向设备发送写入 ack 之前，结果不确定也只做检查。

实际安装的续接入口形式为：

```sh
python3 install.py --resume-manifest /实际安装目录/resume.json
```

这只说明阶段分派规则，不是恢复成功保证；无法连通或身份不符会停止。
revert.py / restore.py 尚未适配 iSH，此包不宣称支持在 iPhone 上恢复原厂。
原厂漏洞仍有上游的出厂状态/初始化约束；只读预检本身不要求重置，不要为预检执行重置。

## 软件验证范围

已在宿主机与 Alpine 3.14 x86、同一 iSH 仓库快照提供的 Python 3.9.16 / OpenSSH 8.6p1
上运行 50 项适配测试，均通过。测试覆盖路由与身份拒绝、接口变化、ART 核对、旧 SCP、
原子阶段保存、掉线后续接、拒绝重复触发，以及模拟 RAM → 永久系统的协调和验证。
上游 selftest 在宿主机重新运行：259 通过，0 失败，1 跳过（缺少原厂镜像输入）。

同一 Alpine 环境中实际运行 iSH 模式的 `--dry-run`，成功下载并验证 v2.0.2 的三个镜像，
且校验 UBI 包含对应 ITB。dry-run 不联系路由器。宿主机 chroot 不模拟 iOS 权限和暂停行为。

用户手机先前已验证 Python、IPv4/IPv6 管理访问、监听及状态持久化；本次进一步观察到
原厂 root 回连、镜像校验与写入回读、RAM SSH、永久系统 overlay 和 ART 指纹校验。
详见 [实机记录](docs/HARDWARE-VALIDATION.zh-CN.md)。iOS 暂停/恢复与 iSH 原厂恢复仍未完整验证。

本机测试入口：

```sh
python3 -m unittest -q test_download_resume test_ish_network test_ish_backend
```

## v0.1.1 下载修复

固件下载改为 2 MiB HTTP Range 请求；短读取或临时网络错误后保留 .part，最多自动重试四次，
重新运行可继续已有进度。服务器忽略 Range 时从头替换该文件，绝不把完整响应追加到旧前缀。
Content-Range 的起止位置和总长度必须吻合；完整长度与可信 SHA-256 都通过后才进入正式缓存。
没有可信摘要的旧辅助资产仍使用完整下载；不允许凭文件大小跳过固件哈希验证。

手机已通过 v0.1.0 的 41 项测试和只读运行环境/状态持久化检查。新增的 9 项真实本地 HTTP
下载测试在宿主机和匹配的旧版 Alpine 环境通过，本次实际安装已使用并通过固件下载与 SHA-256 校验；没有证明所有网络故障下的续传情形都经过手机实测。
