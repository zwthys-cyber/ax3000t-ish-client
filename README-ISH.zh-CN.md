# iPhone 上的刷机工具怎么用

[返回首页](README.md) · [一步步刷机](docs/GUIDE.zh-CN.md) · [常见问题](docs/FAQ.zh-CN.md)

这个工具运行在 iPhone 的 **iSH App** 中。手机负责下载固件、发送命令和检查结果，路由器负责实际写入系统。2026-10-28 已用它在一台小米 AX3000T RD03v2 上完成刷机，并确认正式系统已写入路由器。

想直接操作，先看[一步步刷机教程](docs/GUIDE.zh-CN.md)。本文解释工具的检查、断线后继续操作，以及还没有验证过的情况。

## 先把工具放到手机里

在[工具下载页](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/rd03v2-guide-20261028)下载 `ax3000t-ish-client.zip`，保存到“文件”App 的 **iSH → root**。如果“文件”App 没显示 iSH，可参考 [iSH 官方说明](https://github.com/ish-app/ish/wiki/View-iSH-files-in-Files-App)。

在 iSH 中安装需要的软件并解压：

```sh
apk add python3 openssh-client sshpass openssl ca-certificates unzip
cd /root
unzip ax3000t-ish-client.zip
cd ax3000t-ish-client
python3 ish_preflight.py --runtime --stock-ipv6 'fe80::1%24'
```

最后一行的地址只是格式示例，不能原样照抄：`fe80::…` 要换成你自己路由器的地址，`%24` 要换成当前手机验证得到的接口编号。换 Wi-Fi 后编号可能变化，详细说明见[刷机教程](docs/GUIDE.zh-CN.md)。

ZIP 是手机上的刷机工具，不包含固件。固件另放在[固件下载页](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/firmware-v2.0.2-upstream-mirror)；工具本身仍按原作者提供的信息下载和核对固件。

## 两种“检查”不一样

| 命令 | 会做什么 |
| --- | --- |
| `ish_preflight.py` | 读取路由器信息，检查手机能不能联网、监听端口和保存进度，不给路由器刷机 |
| `install.py --stage preflight` | 为安装取得原厂系统的管理员权限，可能修改原厂配置，但这个阶段还不写固件到闪存 |

第一个检查程序目前要求原厂版本 **2.0.28**。输出 `flash_ready: false` 是正常的，意思是“这个检查本身不能证明可以开始刷机”，不是检查失败。

检查出错就先解决原因，不忽略错误继续。正式安装还要再次核对型号、固件、闪存支持和设备身份。

## 这些检查有什么用？

- 核对 IPv4 和 IPv6 指向的是同一台路由器，避免连错设备。
- 检查路由器能否连回手机，确认手机提供的文件和命令能送达。
- 刷机前读取并比较设备原有的 ART 数据。这是 Wi-Fi 校准等硬件数据，不能拿别人的替换。
- 切换 Wi-Fi 后重新查找路由器地址，而不是一直使用旧地址。
- 写入后读回核对，避免只看到“命令执行了”就当作成功。
- 最后区分临时安装系统和正式系统，确认系统确实写进了路由器。

旧版 iSH 中的 OpenSSH 8.6 使用原来的 SCP 文件传输方式；8.7 及以上由工具加上 `-O`。不需要为了这一步额外安装 SFTP 服务。

## 手机断线或 iSH 被切到后台了怎么办？

iOS 可能暂停后台的 iSH，文件传输和连接等待会中断。不要假定让 App 留在后台就能一直运行。操作时尽量让 iSH 保持前台，给路由器持续供电。

原安装目录里的 **`resume.json` 是进度记录**。它和备份、首次启动配置一起保存，不能删掉，也不要另建一个新安装任务覆盖它。里面可能有私有信息，不能上传公开仓库。

继续操作时，使用原来的记录，形式如下：

```sh
python3 install.py --resume-manifest /实际安装目录/resume.json
```

具体能继续哪一步，取决于已保存的进度：

| 记录里的阶段 | 工具接下来会做什么 |
| --- | --- |
| `exploit-triggering` | 尝试重新接通原连接，不再次触发原厂漏洞；如果原先并未成功触发，就会停止 |
| `preflight-complete` | 重新连上原厂系统，再继续备份和临时系统安装 |
| `pivot-rebooting` / `pivot-complete` | 查找并检查临时系统，不重复写入原厂空闲槽；如果还停在原厂系统，不会直接当作成功 |
| `flash-started` / `flash-complete` | 在 iSH 默认继续流程中只检查安装结果，不再次运行刷写命令 |

已经开始永久刷写后，推荐按主教程使用 `--verify-only` 检查结果。首次核对失败，先看 Wi-Fi、地址和 root 密码，不重新刷一遍。

`revert.py` / `restore.py` 尚未完成 iPhone 恢复原厂的实际验证，不能把“能刷进去”理解成“手机上所有恢复操作也都试过”。原厂漏洞也有版本和初始化状态要求；不要为了运行只读检查就重置路由器。

## 下载中断怎么继续？

v0.1.1 起，固件分成每段 2 MiB 下载。短暂网络错误会保留 `.part` 文件，自动重试最多四次；重新运行时可以接着已有进度下载。

工具还会检查每一段的位置、总大小和最终 SHA-256。SHA-256 是文件完整性校验值，用来确认文件没有下坏或被换掉。服务器不支持分段下载时会重新下载，不能把完整文件误接到旧文件后面。

本次安装已完成固件下载和校验，但不代表所有可能的网络故障都已在手机上测试过。详细历史测试记录见 [ISH_VALIDATION.json](ISH_VALIDATION.json)。

## 已经试过和还没试过的部分

已在本次设备上完成：原厂管理员连接、备份、临时系统启动、SSH 连接、正式系统写入，以及原设备信息和最终系统的检查。见[实际使用记录](docs/HARDWARE-VALIDATION.zh-CN.md)。

尚未完整验证：iOS 在每个阶段暂停后恢复、断电恢复、其他闪存型号，以及通过 iSH 恢复原厂系统。此前的软件测试是在宿主机和 Alpine 环境中进行，不等于 iPhone 真机测试。

开发者可运行已有的软件测试：

```sh
python3 -m unittest -q test_download_resume test_ish_network test_ish_backend
```

工具基于 [ADCDS/xiaomi-openwrt-install](https://github.com/ADCDS/xiaomi-openwrt-install) 的 `2ca24a165a54f11af98cdea1ba8f4fef69c97ec1` 提交。iSH 相关改动尚未合入原作者项目。原始 LICENSE 和 NOTICE 保留。

开发者补充：固定来源的固件设备描述文件用 ART 偏移 6 处的数据设置 LAN MAC，见[该版本源码](https://github.com/ADCDS/openwrt/blob/900aedbd99676c884b09d3138ddc98cf7cd839d0/target/linux/qualcommax/dts/ipq5018-mi-router-ax3000t-v2.dts)。这仅用于生成候选地址，不保证以后所有固件的地址都一样。
