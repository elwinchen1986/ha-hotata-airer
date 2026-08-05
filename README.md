# Hotata Airer (好太太智能晾衣机)

[![GitHub Release](https://img.shields.io/github/v/release/C3H3-AI/ha-hotata-airer?style=flat-square)](https://github.com/C3H3-AI/ha-hotata-airer/releases)
[![GitHub Downloads](https://img.shields.io/github/downloads/C3H3-AI/ha-hotata-airer/total?style=flat-square)](https://github.com/C3H3-AI/ha-hotata-airer/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat-square)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-blue?style=flat-square)](https://www.home-assistant.io/)
[![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-green?style=flat-square)](LICENSE)

Home Assistant 自定义集成，支持好太太智能晾衣机的完整控制。

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 晾衣架升降 | cover 实体，支持开/关/停和位置模拟 |
| 照明控制 | light 实体，支持开关和亮度调节 |
| 电源/烘干/风干/消毒/负离子 | switch 实体，独立控制 |
| 定时提醒 | sensor 实体，显示各功能剩余时间 |
| 在线状态 | binary_sensor 实体，设备连接状态 |
| 下降时长配置 | number 实体，配置全程下降时间 |
| 位置重置 | button 实体，校准模拟位置 |
| 自动 Token 刷新 | 双层保障：refreshToken 定期刷新 + 失效后自动用账号密码重登录 |
| 用户名密码登录 | v3.0 新增，无需再从小程序抓包获取 refreshToken |
| 多设备支持 | 可添加多台好太太晾衣机 |

---

## 安装方式

### 方式一：HACS（推荐）

[![Open in HACS](https://img.shields.io/badge/Open%20in-HACS-41BDF5?style=flat-square)](https://my.home-assistant.io/redirect/hacs_repository/?owner=C3H3-AI&repository=ha-hotata-airer)

1. 安装 [HACS](https://hacs.xyz/)
2. HACS → 集成 → 右上角三点菜单 → 添加自定义存储库
3. 仓库地址：`https://github.com/C3H3-AI/ha-hotata-airer`
4. 搜索并安装 **Hotata Airer**
5. 重启 Home Assistant

### 方式二：手动安装

```bash
# 克隆仓库
git clone https://github.com/C3H3-AI/ha-hotata-airer.git

# 复制到 HA 自定义组件目录
cp -r custom_components/hotata_airer /path/to/your/ha/config/custom_components/

# 重启 HA
```

---

## 配置

集成通过 UI 配置，无需编辑 YAML。

1. **配置 → 设备与服务 → 添加集成**
2. 搜索 **Hotata Airer**
3. 输入好太太智联 App 的**账号（手机号）和密码**

### 配置参数

| 参数 | 说明 |
|------|------|
| 用户名 | 必填，好太太智联 App 注册手机号 |
| 密码 | 必填，好太太智联 App 登录密码 |
| 下降时长 | 可选，晾衣架从顶到底所需秒数（默认 10s） |

> **提示**：登录成功后自动发现该账号下所有晾衣机设备，无需手动输入设备信息。

### Token 自动刷新机制

集成采用双层保障，无需手动干预：

1. **refreshToken 定期刷新**：每 6 小时自动用 refreshToken 换取新的 accessToken
2. **自动重登录**：当 refreshToken 也失效时（如服务器侧过期），自动用保存的账号密码重新登录获取新 token

仅在账号密码被修改导致重登录失败时，才会发送通知提醒你更新密码。

---

## 实体列表

### binary_sensor（状态传感器）

| translation_key | 默认名称 | 说明 |
|----------------|---------|------|
| `online_status` | 在线状态 | 设备是否在线 |
| `power` | 电源开关 | 电源是否开启 |

### cover（晾衣架）

| translation_key | 默认名称 | 说明 |
|----------------|---------|------|
| `cover` | 晾衣机 | 晾衣架升降控制（开/关/停/位置） |

### light（照明）

| translation_key | 默认名称 | 说明 |
|----------------|---------|------|
| `light` | 照明 | 灯光开关和亮度控制 |

### sensor（传感器）

| translation_key | 默认名称 | 说明 |
|----------------|---------|------|
| `position` | 位置 | 当前晾衣架模拟位置（0-100%） |
| `light_remaining_time` | 灯光定时 | 照明定时剩余分钟数 |
| `drying_remaining_time` | 烘干定时 | 烘干定时剩余分钟数 |
| `air_drying_remaining_time` | 风干定时 | 风干定时剩余分钟数 |
| `disinfection_remaining_time` | 消毒定时 | 消毒定时剩余分钟数 |
| `ions_remaining_time` | 负离子定时 | 负离子定时剩余分钟数 |
| `motor_control_mode` | 电机状态 | 当前运行模式（停止/上升/下降） |
| `error_state` | 异常状态 | 集成异常描述信息 |

### switch（开关）

| translation_key | 默认名称 | 说明 |
|----------------|---------|------|
| `power` | 电源 | 总电源开关 |
| `drying` | 烘干 | 烘干功能开关 |
| `air_drying` | 风干 | 风干功能开关 |
| `disinfection` | 消毒 | 消毒功能开关 |
| `ions` | 负离子 | 负离子功能开关 |

### number（配置）

| translation_key | 默认名称 | 说明 |
|----------------|---------|------|
| `descent_time` | 下降时长 | 晾衣架全程下降时间（秒） |

### button（操作）

| translation_key | 默认名称 | 说明 |
|----------------|---------|------|
| `reset_position` | 重置位置 | 重置模拟位置为 100%（已升起） |

---

## 选项配置

集成支持运行时修改参数，无需重新配置：

- **下降时长（秒）**：设置晾衣架从完全升起到完全降下的总时长，0 表示禁用位置模拟

---

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 实体不出现 | 重启 HA，检查账号密码是否正确 |
| 设备离线 | 检查网络连接，确认设备是否在线 |
| 控制无响应 | 查看 HA 日志中的 `hotata_airer` 相关错误 |
| 登录失败 | 确认好太太智联 App 账号密码是否正确，可通过重新配置更新 |
| 收到"登录已失效"通知 | 账号密码可能已修改，点击集成重新配置，输入新密码 |

## 💝 赞助

如果这个集成帮到了你，欢迎请我喝杯咖啡 ☕

| 微信支付 | 支付宝 |
|:--------:|:------:|
| ![微信](sponsor/wechat.jpg) | ![支付宝](sponsor/alipay.jpg) |

---

## 版本历史

| 版本 | 说明 |
|------|------|
| **v3.0.2** | 所有登录错误提示都附带服务器原始 message，让用户看到完整失败原因 |
| **v3.0.1** | 修复登录失败提示不精确的问题：区分「手机号未注册」「密码错误」「验证码 required」「账号锁定」「频繁」等错误码，避免用户误判为密码错误去重置密码 |
| **v3.0.0** | **重大升级**：支持用户名/密码直接登录（逆向好太太 App 登录协议，AES 加密 + RSA 签名），无需再从小程序抓包获取 refreshToken。新增 refreshToken 失效后自动重登录机制，双层保障 token 永久有效。支持从 v2 配置项自动迁移 |
| **v2.3.0** | **重大重构**：采用小米式单账号模型——refreshToken 仅输入一次、自动拉取云端设备列表、一账号多设备共享 token。新增自动发现新设备 + 新设备通知 + token 过期通知功能 |
| **v2.3.2** | 修复卸载失败 bug（async_forward_entry_unloads 不存在的方法名） |
| **v2.2.0** | **两大重磅更新**：多设备支持（可添加多台晾衣机）+ 下降时长设置（可配置模拟位置精度）。另新增 button 重置位置、诊断支持、选项配置、完善翻译 |
| **v2.1.1** | 修复 Token 刷新机制，兼容 HA 2026 |
| **v2.1.0** | 同步本地最新版本，优化 Token 刷新机制 |
| **v2.0.0** | 初始公开版本 |


## License

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)

---

Made with ❤️ by [C3H3-AI](https://github.com/C3H3-AI)
