# 用 iPhone 一步步给小米 AX3000T RD03v2 刷机

[返回首页](../README.md) · [OpenClash 后续配置](OPENCLASH.zh-CN.md) · [本次验证范围](HARDWARE-VALIDATION.zh-CN.md)

这份教程记录了 2026-10-28 用 iPhone 给一台小米 RD03v2 刷入 v2.0.2 固件的过程。

有些命令要在手机上运行，有些要先登录路由器才能运行。输入前先看命令行左边的提示：

| 提示符 | 所在设备 |
| --- | --- |
| `localhost:~#` | iPhone 的 iSH |
| `root@OpenWrt:~#` | SSH 登录后的路由器 |

查看路由器空间、日志和内存时，要先登录路由器。也就是运行 `df /overlay`、`logread`、`free` 之前，应看到 `root@OpenWrt:~#`。手机 iSH 中的 `free` 显示 0，不代表路由器没有内存。

## 1. 看清型号，准备手机上的工具

先确认型号为 **RD03v2，处理器是高通 IPQ5018**，不要只看外壳上的 AX3000T。

本次设备的闪存芯片是 ESMT F50D1G41LB，工具显示 `flash_type=0x11`，v2.0.2 支持这款芯片。其他芯片也要让工具检查通过，不能照着别人的结果跳过检查。

手机连接原厂 Wi-Fi，iSH 保持前台。安装手机侧依赖、获取本仓库：

```sh
apk add python3 openssh-client sshpass openssl ca-certificates curl unzip git
cd /root
git clone --branch main https://github.com/zwthys-cyber/ax3000t-ish-client.git
cd /root/ax3000t-ish-client
```

如果已经开始刷机，请保留原目录和里面的 `resume.json`。这是工具保存的安装进度，不能用新安装覆盖。也可以到下载页 [Releases](https://github.com/zwthys-cyber/ax3000t-ish-client/releases) 获取。

先让工具下载并检查固件。下面这一步只下载文件，不连接路由器，也不刷机：

```sh
python3 install.py standard --release v2.0.2 --network-backend ish --interface ish-wifi --transport wifi --dry-run
```

命令中的 `standard` 沿用本次操作的写法；v2.x 实际只有一套固件。工具会核对文件的 SHA-256，并检查两个临时系统文件是否配套。只有检查通过才能继续。

## 2. 先检查手机能不能连接路由器

本仓库的 `ish_preflight.py` 当前明确要求原厂版本 **2.0.28**；这是代码中的检查条件。
其他原厂版本不能只凭同型号就跳过失败继续。是否支持及初始化约束以安装器的对应版本说明为准。

在 iPhone 设置 → Wi-Fi → 当前网络右侧 ⓘ 中，查看 IPv6 路由器地址。

下面命令的地址带有 `%24` 这样的结尾，它是手机当前网络的接口编号。地址和编号都要用你自己的；不能照抄别人日志里的值，换 Wi-Fi 后也可能变化。

把下面的 `fe80::1%24` 替换成**你已确认的地址和数字 scope**后运行：

```sh
python3 ish_preflight.py --runtime --stock-ipv6 'fe80::1%24'
```

这一步只检查，不取得路由器管理员权限，也不写固件。看到 `flash_ready: false` 是正常的，表示这个检查本身还不能证明可以开始刷机。

## 3. 取得路由器管理员权限，检查能否安装

这一步与上面的只读检查不同：工具会取得原厂系统的管理员权限（root），也可能修改原厂设置。屏幕上的 “nothing is written” 只表示这个阶段还没向闪存写入固件。

原厂版本和初始化状态必须符合[原作者的安装要求](https://github.com/ADCDS/xiaomi-openwrt-install)。如果之前已经执行过一次，请按保存的进度继续，不反复触发原厂漏洞。

仍将示例 IPv6 地址替换为自己确认的地址：

```sh
python3 install.py standard --release v2.0.2 \
  --network-backend ish --interface ish-wifi --transport wifi \
  --ish-stock-ipv6 'fe80::1%24' --configure \
  --outdir /root/ax3000t-ish-client/ish-live --stage preflight
```

交互输入永久系统的 root 密码、SSID、Wi-Fi 密码和实际所在地国家码。**root 登录密码与 Wi-Fi 密码是两项不同设置**；WPA2 密码须为 8～63 个可打印 ASCII 字符。本次永久 SSID 使用 `OpenWrt-AX3000T`。不要把密码写进公开脚本或 GitHub。

工具会检查现有系统所在位置、准备写入的位置、文件大小、可用空间和所需程序。

本次路由器正在运行 `rootfs`，准备写入的是空闲的 `rootfs_1`。两个位置各有 31,457,280 字节空间，能装下 17,432,576 字节的临时系统文件。检查通过后再继续，不能照抄这些数字去手动刷写。

## 4. 先启动临时安装系统

仅在原安装记录已经完成预检、安装器明确提示该续接命令时运行：

```sh
python3 /root/ax3000t-ish-client/install.py standard --stage pivot --skip-exploit \
  --resume-manifest /root/ax3000t-ish-client/ish-live/resume.json
```

工具会先保存路由器的启动设置和硬件数据备份，包括 APPSBLENV、ART、bdata、APPSBL 和 U-Boot 环境。ART 里有 Wi-Fi 等硬件的校准数据，工具会核对它确实来自本机。

这些备份应再保存一份到自己的私人存储，不能上传公开仓库，也不能拿别人的备份替换。

写入确认要求完整输入大写 **`YES`**，输入 `y` 会取消。本次写入空闲槽后回读 **16,633,856 字节**，与对应镜像 MD5 一致，才设置启动标志。这里的槽编号和长度是本次记录，不能拿来手动拼 `mtd` / `ubiformat` 命令。

按提示确认重启后，在 iPhone 设置连接：

- 临时 SSID：`OpenWrt-RD03v2-Installer`
- 该版本临时安装网络密钥：`rd03v2install`

这是临时安装用的 Wi-Fi，和安装完成后使用的 Wi-Fi 不同。连接后返回 iSH，按提示填写当前网络实际的 IPv6 路由器地址。

此时原厂系统还保留着；**下一步正式写入后，原厂双槽布局会被接管，不能再依赖原厂系统自动回退**。

## 5. 把正式系统写进路由器

```sh
python3 /root/ax3000t-ish-client/install.py standard --stage flash \
  --resume-manifest /root/ax3000t-ish-client/ish-live/resume.json
```

出现 `OpenWrt root password used by the original run:` 时，输入第 3 步设置的 **root 密码**；输入时终端不显示字符是正常的。

输入最终确认前，工具必须确认下面几件事。括号中的英文是日志里的原文，方便对照：

- 设备型号正确，而且正在运行临时系统：`board_name=xiaomi,mi-router-ax3000t-v2`、`rootfs_type=tmpfs`。
- 设备硬件数据与原备份一致，闪存芯片受支持，正式固件检查通过。
- 上传后的文件完整，系统的试检查命令 `sysupgrade -T` 认可这个固件。

最终输入 `YES` 后，工具会重新建立系统存储区域，写入内核和系统文件，然后重启。**保持供电，不重复发起刷写。永久安装会接管原厂双槽布局，不能再期待原厂槽自动回退。**

临时网络消失后，连接你设置的永久 Wi-Fi（本次为 `OpenWrt-AX3000T`），密码是自己配置的永久 Wi-Fi 密码。

## 6. 检查是否成功；掉线后不要立即重刷

如果安装末尾 SSH 认证失败或超时，但永久 Wi-Fi 已出现，不要重新刷。先接对 Wi-Fi、确认 root 密码，再运行只读校验：

```sh
python3 /root/ax3000t-ish-client/install.py \
  --verify-only /root/ax3000t-ish-client/ish-live/resume.json
```

本次首次验证误用了密码而失败；使用正确 root 密码后得到：

```text
original device ART fingerprint matched
installed board=xiaomi,mi-router-ax3000t-v2 rootfs_type=overlay
[+] OpenWrt is installed on NAND.
```

只看到 SSH 有响应或 ping 通，还不能证明正式系统已经写入。上面的 `rootfs_type=overlay` 是本次成功核对的一部分。记录已经是 `flash-started` 时，只继续检查，不再重复运行 `sysupgrade`。

## 7. 插好网线，避免两个路由器地址冲突

本次一开始用 `192.168.1.1` 打开管理页面。没插网线时，WAN（接外网的接口）显示 **Carrier: Absent**，意思是没有检测到网线连接，所以下载软件失败。

把上一级路由器的 LAN 口接到小米路由器的 WAN 口后，小米 WAN 获得了 `192.168.1.2/24`。但它给手机使用的 LAN 仍是 `192.168.1.1/24`，两边都在 `192.168.1.x`，需要改其中一边。本次选择修改小米的 LAN。

在 LuCI → **Network → Interfaces → lan → Edit**，修改 **IPv4 address**：

```text
192.168.10.1/24
```

这是 LAN 地址，保留 `Static address` 和 `br-lan`。WAN 保留 DHCP client。LAN 的 gateway 一栏可能显示从 WAN 获得的灰色提示，不要把上游地址抄进 LAN 网关。

点击 **Save → Save & Apply** 后连接会切断：重新连接 Wi-Fi，手机重新获取 `192.168.10.x` 地址，在浏览器访问 `http://192.168.10.1`，完成应用确认。如 90 秒无法确认而回滚，等回滚完成、回到旧地址检查，再重新操作；不要在不确定当前地址时反复更改配置。本次最终已成功改为 `192.168.10.1`。

## 8. 把管理页面改成中文

先在 System → Software 点击 **Update lists**；成功应看到类似 `OK: 10012 distinct packages available`。

可在软件页面搜索并安装下列包，或在**路由器 SSH**中运行：

```sh
apk update
apk add luci-i18n-base-zh-cn luci-i18n-firewall-zh-cn luci-i18n-package-manager-zh-cn
```

安装后重新登录或刷新，在 System → System → Language and Style 选择简体中文（未自动切换时）。继续阅读 [OpenClash 安装与排错](OPENCLASH.zh-CN.md)。

## 9. 为什么有两个同名 Wi-Fi

管理页面中的 `radio0` 是 2.4 GHz，覆盖距离较远；`radio1` 是 5 GHz，近距离通常速度更快。两边用同一个 Wi-Fi 名称（SSID）时，iPhone 通常只显示一个，由手机选择连接哪边。

在“已连接站点”里可以看实际连接情况。本次 iPhone 连的是 5 GHz，页面显示约 1080/1201 Mbit/s 的无线连接速率；这表示手机和路由器之间的连接，不等于外网上网速度。
