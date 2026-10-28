# 小米 AX3000T RD03v2：从 iPhone 刷机到可用网络

[返回首页](../README.md) · [OpenClash 后续配置](OPENCLASH.zh-CN.md) · [本次验证范围](HARDWARE-VALIDATION.zh-CN.md)

本文记录 2026-10-28 一台高通 RD03v2 使用固件 v2.0.2 的成功过程。命令分为手机 iSH 和路由器 SSH 两个环境，操作前看清提示符：

| 提示符 | 所在设备 |
| --- | --- |
| `localhost:~#` | iPhone 的 iSH |
| `root@OpenWrt:~#` | SSH 登录后的路由器 |

`df /overlay`、`logread`、路由器 `free` 等诊断必须在第二个环境运行。手机 iSH 的 `free` 显示 0 不代表路由器没有内存。

## 1. 准备与版本确认

确认型号为 **RD03v2 / Qualcomm IPQ5018**；不能只看外壳上的 AX3000T。本文实机 `flash_type=0x11`，ESMT F50D1G41LB，由 v2.0.2 安装器的支持表通过检查。其他芯片必须以所选版本的检查结果为准。

手机连接原厂 Wi-Fi，iSH 保持前台。安装手机侧依赖、获取本仓库：

```sh
apk add python3 openssh-client sshpass openssl ca-certificates curl unzip git
cd /root
git clone --branch ish-support https://github.com/zwthys-cyber/ax3000t-ish-client.git
cd /root/ax3000t-ish-client
```

已有目录请继续使用原目录与原 `resume.json`，不要用新的安装覆盖续接状态。下载包也可从 [Releases](https://github.com/zwthys-cyber/ax3000t-ish-client/releases) 获取。

先运行完全不连接路由器的镜像下载校验：

```sh
python3 install.py standard --release v2.0.2 --network-backend ish --interface ish-wifi --transport wifi --dry-run
```

`standard` 是本次实际命令沿用的参数；v2.x 由发布元数据选择其单一固件。镜像必须经过可信 SHA-256 及 UBI/ITB 对应校验。

## 2. 只读手机预检

本仓库的 `ish_preflight.py` 当前明确要求原厂版本 **2.0.28**；这是代码中的检查条件。
其他原厂版本不能只凭同型号就跳过失败继续。是否支持及初始化约束以安装器的对应版本说明为准。

查看 iPhone 设置 → Wi-Fi → 当前网络右侧 ⓘ 的 IPv6 路由器地址。iSH 访问 link-local 地址需要原生数字 scope，必须通过当前设备验证取得；不能照抄别人日志里的 `%24`，换网络后也可能变化。

把下面的 `fe80::1%24` 替换成**你已确认的地址和数字 scope**后运行：

```sh
python3 ish_preflight.py --runtime --stock-ipv6 'fe80::1%24'
```

这是只读检查，`flash_ready: false` 不表示故障。它不会取得 root 或写 NAND。

## 3. 取得 root 并完成安装器预检

`install.py --stage preflight` 与上一步不同：它会取得原厂 root、可能修改原厂配置。其“nothing is written”指该阶段不写 NAND，不表示整个命令对原厂系统零修改。原厂固件、初始化状态须满足[上游安装器](https://github.com/ADCDS/xiaomi-openwrt-install)要求；若一次性触发已使用，按续接记录处理，不能盲目重复触发。

仍将示例 IPv6 地址替换为自己确认的地址：

```sh
python3 install.py standard --release v2.0.2 \
  --network-backend ish --interface ish-wifi --transport wifi \
  --ish-stock-ipv6 'fe80::1%24' --configure \
  --outdir /root/ax3000t-ish-client/ish-live --stage preflight
```

交互输入永久系统的 root 密码、SSID、Wi-Fi 密码和实际所在地国家码。**root 登录密码与 Wi-Fi 密码是两项不同设置**；WPA2 密码须为 8～63 个可打印 ASCII 字符。本次永久 SSID 使用 `OpenWrt-AX3000T`。不要把密码写进公开脚本或 GitHub。

本次预检确认：运行 `rootfs`，目标空闲槽为 `rootfs_1`；两槽各 31,457,280 字节，17,432,576 字节镜像能够装下；运行槽与已挂载 UBI 不会被误写，工具和临时空间检查通过。

## 4. 写入空闲槽，进入 RAM 安装系统

仅在原安装记录已经完成预检、安装器明确提示该续接命令时运行：

```sh
python3 /root/ax3000t-ish-client/install.py standard --stage pivot --skip-exploit \
  --resume-manifest /root/ax3000t-ish-client/ish-live/resume.json
```

安装器先备份 APPSBLENV、ART、bdata、APPSBL 和 U-Boot 环境，再检查 ART 一致性。备份包含设备私有数据，要保存到另一处私人存储，不上传仓库。

写入确认要求完整输入大写 **`YES`**，输入 `y` 会取消。本次写入空闲槽后回读 **16,633,856 字节**，与对应镜像 MD5 一致，才设置启动标志。这里的槽编号和长度是本次记录，不能拿来手动拼 `mtd` / `ubiformat` 命令。

按提示确认重启后，在 iPhone 设置连接：

- 临时 SSID：`OpenWrt-RD03v2-Installer`
- 该版本临时安装网络密钥：`rd03v2install`

临时安装网络与永久 Wi-Fi 不同。返回 iSH，按提示提供当前网络真实的 IPv6 路由器地址。此时原厂槽仍在；**这个回退条件只适用于 pivot，不能套用到下一步永久安装之后**。

## 5. 从 RAM 系统安装到 NAND

```sh
python3 /root/ax3000t-ish-client/install.py standard --stage flash \
  --resume-manifest /root/ax3000t-ish-client/ish-live/resume.json
```

出现 `OpenWrt root password used by the original run:` 时，输入第 3 步设置的 **root 密码**；输入时终端不显示字符是正常的。

确认写入前，安装器必须检查：

- `board_name=xiaomi,mi-router-ax3000t-v2`、`rootfs_type=tmpfs`，证明是正确 RAM 系统。
- 原设备 ART 指纹匹配，NAND 探测和永久镜像支持检查通过。
- 上传固件校验通过，`sysupgrade -T` 接受镜像。

最终确认输入 `YES` 后，安装器重建 UBI、写 kernel/rootfs 并重启。**保持供电，不重复发起刷写。永久安装会接管原厂双槽布局，不能再期待原厂槽自动回退。**

临时网络消失后，连接你设置的永久 Wi-Fi（本次为 `OpenWrt-AX3000T`），密码是自己配置的永久 Wi-Fi 密码。

## 6. 校验永久系统；验证掉线不等于刷机失败

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

只有 banner 或 ping 通不能证明装到了 NAND。`flash-started` 状态只继续校验，不重放 `sysupgrade`。

## 7. 接通 WAN，消除上下游网段冲突

本次初始管理地址为 `192.168.1.1`。网线没插时 WAN 显示 **Carrier: Absent**，软件包下载失败。将上游路由器 LAN 接入本机 WAN 后，WAN 获得 `192.168.1.2/24`，但 LAN 也是 `192.168.1.1/24`，上下游发生网段冲突。

在 LuCI → **Network → Interfaces → lan → Edit**，修改 **IPv4 address**：

```text
192.168.10.1/24
```

这是 LAN 地址，保留 `Static address` 和 `br-lan`。WAN 保留 DHCP client。LAN 的 gateway 一栏可能显示从 WAN 获得的灰色提示，不要把上游地址抄进 LAN 网关。

点击 **Save → Save & Apply** 后连接会切断：重新连接 Wi-Fi，手机重新获取 `192.168.10.x` 地址，在浏览器访问 `http://192.168.10.1`，完成应用确认。如 90 秒无法确认而回滚，等回滚完成、回到旧地址检查，再重新操作；不要在不确定当前地址时反复更改配置。本次最终已成功改为 `192.168.10.1`。

## 8. 安装中文界面

先在 System → Software 点击 **Update lists**；成功应看到类似 `OK: 10012 distinct packages available`。

可在软件页面搜索并安装下列包，或在**路由器 SSH**中运行：

```sh
apk update
apk add luci-i18n-base-zh-cn luci-i18n-firewall-zh-cn luci-i18n-package-manager-zh-cn
```

安装后重新登录或刷新，在 System → System → Language and Style 选择简体中文（未自动切换时）。继续阅读 [OpenClash 安装与排错](OPENCLASH.zh-CN.md)。

## 9. 两个同名 Wi-Fi 是什么

`radio0` 的 2.4 GHz 和 `radio1` 的 5 GHz 都可启用，使用同一个 SSID 时，iPhone Wi-Fi 列表通常合并成一项，由手机选频段。LuCI“已连接站点”可查看实际连接的 radio。本次 iPhone 连到 5 GHz、80 MHz、双流，显示约 1080/1201 Mbit/s 的链路速率；这不是互联网测速结果。
