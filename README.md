# 用 iPhone 给小米 AX3000T RD03v2 刷 OpenWrt

这是一份中文刷机教程，记录了怎样用 iPhone 给小米 AX3000T RD03v2 安装 OpenWrt，再安装中文管理页面和 OpenClash。里面有操作步骤、固件下载，以及这次遇到的问题和解决办法。

**已在一台路由器上完成安装并正常使用。** OpenClash 安装后曾出现网页打开慢的问题，修复 DNS 设置后，用户确认明显变快。其他硬件版本或不同软件版本，仍需先检查是否兼容。

## 先确认你的路由器型号

适用的是 **小米 AX3000T RD03v2，高通 IPQ5018 处理器**。

同样叫 AX3000T 的旧版 RD03 / RD23 使用不同硬件，不能用这里的固件。不要只看商品名称，要核对型号。本次使用的固件版本是 **v2.0.2**。

## 你想做什么？

| 要做的事 | 点这里 |
| --- | --- |
| 从原厂系统开始刷机 | [一步步刷机教程](docs/GUIDE.zh-CN.md) |
| 安装 OpenClash，解决安装和上网问题 | [OpenClash 安装教程](docs/OPENCLASH.zh-CN.md) |
| 下载固件 | [v2.0.2 固件下载](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/firmware-v2.0.2-upstream-mirror) |
| 下载在 iPhone 上运行的刷机工具 | [工具下载页](https://github.com/zwthys-cyber/ax3000t-ish-client/releases/tag/rd03v2-guide-20261028)，选择 `ax3000t-ish-client.zip` |
| 看不懂教程中的英文缩写 | [用简单的话解释常见术语](docs/TERMS.zh-CN.md) |
| 不知道下载哪个文件、密码填什么 | [常见问题](docs/FAQ.zh-CN.md) |
| 查看所用版本和文件校验值 | [下载文件与版本说明](docs/ARTIFACTS.zh-CN.md) |
| 了解手机上的检查和断线后如何继续 | [iPhone 使用说明](README-ISH.zh-CN.md) |
| 参考一份不含真实账号的配置 | [OpenClash 配置示例](examples/mihomo.example.yaml)，需填自己的节点信息 |
| 查看这次实际完成了哪些操作 | [实际使用记录](docs/HARDWARE-VALIDATION.zh-CN.md) |
| 查看文档更新 | [更新记录](docs/CHANGELOG.zh-CN.md) |

仓库只保留默认的 **`main` 分支**，打开就能看，不用切换分支。GitHub 下载页叫 **Releases**，里面的 **Assets** 就是附件列表。固件和刷机工具是分开下载的。

## 开始前需要知道

- iPhone 上使用 **iSH**，也就是输入和运行命令的终端 App。
- **OpenWrt** 是将要安装到路由器上的系统；**LuCI** 是它的网页管理界面。
- **OpenClash** 是安装在 OpenWrt 上的插件，需要你自己提供节点或订阅。下载的原版固件没有预装它。
- 刷机过程中会先启动一个临时系统，再把正式系统写入路由器。按教程顺序操作，不能把任意文件直接上传到小米原厂升级页面。
- 操作会更换路由器系统。先读 [操作说明与风险提示](NOTICE)，保存好自己的备份，保持供电，不跳过工具的型号和文件检查。
- 手机上断线不一定意味着刷机失败。已经开始写入后，先按教程检查结果，不要立即再刷一遍。

## 版本与来源

本次使用 OpenWrt v2.0.2 和 OpenClash v0.48.002。固件下载页保存的是原版文件；iPhone 上的刷机适配、中文教程和本次操作记录在这里维护。

软件的基础项目、完整源码和许可证集中放在[软件来源说明](docs/SOURCES.zh-CN.md)，需要检查来源时可以查看。

## 给需要核对技术细节的人

本次路由器的闪存型号为 ESMT F50D1G41LB，`flash_type=0x11`。刷机工具保留了型号、闪存支持、原设备信息和文件完整性检查。安装完成后，工具确认运行的是已写入路由器的系统，而不只是临时系统。

此前已通过 50 项适配与断线恢复模拟测试；基础安装器的软件检查为 259 通过、0 失败、1 跳过。Alpine 3.14 x86 / Python 3.9.16 / OpenSSH 8.6p1 环境也通过了适配测试。详细结果见 [ISH_VALIDATION.json](ISH_VALIDATION.json)。软件模拟通过不代表所有手机中断、断电或恢复原厂的情况都已在真机上试过。

```sh
python3 -m unittest -q test_download_resume test_ish_network test_ish_backend
```

程序工作方式见[技术说明](docs/technical.md)，软件来源与署名见[来源说明](docs/SOURCES.zh-CN.md)。[NOTICE](NOTICE) 与 [GPL-2.0 许可证](LICENSE) 保留。`revert.py` / `restore.py` 在 iPhone 上恢复原厂系统的流程尚未完成实际验证。
