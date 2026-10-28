# AX3000T RD03v2：iPhone iSH 实验适配

这是客户端源代码验证包。完整安装路径已经接入 iSH 后端，但没有在 iPhone 上完成从原厂到
OpenWrt 的端到端刷写。现在只执行下面的只读预检，不重置、不触发漏洞、不启动刷机。

基础项目：ADCDS/xiaomi-openwrt-install，固定提交
`2ca24a165a54f11af98cdea1ba8f4fef69c97ec1`。
本仓库的 iSH 后端、只读预检、续接记录与相关测试为实验适配，尚未合入上游。
原始 LICENSE、NOTICE 保留。固件由上游 release.py 下载验证，本包不包含固件镜像。

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
把检查结果发回后再决定下一项验证。当前不要执行 install.py 的实际安装入口。
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

后续实际验证时的续接入口形式为：

```sh
python3 install.py --resume-manifest /实际安装目录/resume.json
```

这只说明阶段分派规则，不是恢复成功保证；无法连通或身份不符会停止。
revert.py / restore.py 尚未适配 iSH，此包不宣称支持在 iPhone 上恢复原厂。
原厂漏洞仍有上游的出厂状态/初始化约束；本次预检不要求重置，当前也不要重置。

## 软件验证范围

已在宿主机与 Alpine 3.14 x86、同一 iSH 仓库快照提供的 Python 3.9.16 / OpenSSH 8.6p1
上运行 41 项适配测试，均通过。测试覆盖路由与身份拒绝、接口变化、ART 核对、旧 SCP、
原子阶段保存、掉线后续接、拒绝重复触发，以及模拟 RAM → 永久系统的协调和验证。
上游 selftest 在宿主机重新运行：259 通过，0 失败，1 跳过（缺少原厂镜像输入）。

同一 Alpine 环境中实际运行 iSH 模式的 `--dry-run`，成功下载并验证 v2.0.2 的三个镜像，
且校验 UBI 包含对应 ITB。dry-run 不联系路由器。宿主机 chroot 不模拟 iOS 权限和暂停行为。

用户手机已经实测：Python 安装、IPv4 管理访问和本地监听、IPv6 单播 HTTP、两个地址的
设备标识一致。尚未实测：新预检的文件持久化、OpenSSH 的实际设备连接、路由器向手机
回连、RAM 启动与永久系统的完整安装。不能把软件测试通过称为手机刷机成功。

本机测试入口：

```sh
python3 -m unittest -q test_ish_network test_ish_backend
```
