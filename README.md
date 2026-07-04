# Hotata Airer (好太太智能晾衣机)

[![GitHub Release](https://img.shields.io/github/v/release/C3H3-AI/ha-hotata-airer?style=flat-square)](https://github.com/C3H3-AI/ha-hotata-airer/releases)
[![GitHub Downloads](https://img.shields.io/github/downloads/C3H3-AI/ha-hotata-airer/total?style=flat-square)](https://github.com/C3H3-AI/ha-hotata-airer/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat-square)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue?style=flat-square)](https://www.home-assistant.io/)
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
| 自动 Token 刷新 | 无需手动干预，长期稳定运行 |
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
3. 填入从微信好太太小程序网络请求中获取的 **refreshToken**

### 配置参数

| 参数 | 说明 |
|------|------|
| refreshToken | 必填，从微信好太太小程序网络请求中获取 |
| 设备名称 | 可选，设备显示名称 |
| 下降时长 | 可选，晾衣架从顶到底所需秒数（默认 10s） |

> **提示**：只需提供 refreshToken，其他参数可后续在选项中修改。

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
| 实体不出现 | 重启 HA，检查 refreshToken 是否正确 |
| 设备离线 | 检查网络连接，确认 token 未过期 |
| 控制无响应 | 查看 HA 日志中的 `hotata_airer` 相关错误 |
| Token 失效 | 重新配置集成，输入新的 refreshToken |

---

## 版本历史

| 版本 | 说明 |
|------|------|
| **v2.2.0** | **两大重磅更新**：多设备支持（可添加多台晾衣机）+ 下降时长设置（可配置模拟位置精度）。另新增 button 重置位置、诊断支持、选项配置、完善翻译 |
| **v2.1.1** | 修复 Token 刷新机制，兼容 HA 2026 |
| **v2.1.0** | 同步本地最新版本，优化 Token 刷新机制 |
| **v2.0.0** | 初始公开版本 |


## License

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)

---

Made with ❤️ by [C3H3-AI](https://github.com/C3H3-AI)