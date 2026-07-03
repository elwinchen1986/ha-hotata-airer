# 好太太晾衣架 App 逆向工程报告

> 最后更新: 2026-06-25  
> 目标平台: 好太太智家微信小程序（miniapp）/ 好太太智联 Android App (v3.5.8)  
> 仓库: https://github.com/C3H3-AI/ha-hotata-airer

---

## 目录

1. [逆向方式](#1-逆向方式)
2. [API 架构概览](#2-api-架构概览)
3. [认证协议](#3-认证协议)
4. [签名算法](#4-签名算法)
5. [API 端点详解](#5-api-端点详解)
6. [设备属性图谱](#6-设备属性图谱)
7. [控制命令](#7-控制命令)
8. [完整数据流](#8-完整数据流)
9. [集成架构](#9-集成架构)
10. [APK 逆向分析](#10-apk-逆向分析)
11. [进一步可探索方向](#11-进一步可探索方向)

---

## 1. 逆向方式

### 1.1 当前使用的逆向方法

当前集成基于 **微信小程序 "好太太智家/好太太智慧家" 的网络抓包**，而非直接反编译 Android APK。

- **APP_KEY**: `miniapp-hotata-prod`（前缀 `miniapp-` 暴露了来源是微信小程序）
- **协议层**: HTTP/HTTPS → `saas.keyoo.com`
- **抓包工具**: 基于微信小程序的 HTTPS 流量拦截

### 1.2 APK 逆向完成情况

| 方法 | 说明 | 状态 |
|------|------|------|
| 微信小程序抓包 | Proxyman/Charles 拦截小程序 HTTPS 流量 | ✅ 已使用 |
| Android APK 反编译 | Jadx v1.5.5 反编译 `com.hotata.keyoolot` (v3.5.8, 105MB) | ✅ 已完成 — 360加固，6个Java壳文件 |
| Native .so strings 分析 | 5个核心库文件完整 strings 提取 | ✅ 已完成 |
| APK assets 提取 | 配网配置、Lottie UI动画、证书文件 | ✅ 已完成 |
| HA 端流量捕获 | tcpdump + 触发脚本验证网络流向 | ✅ saas.keyoo.com:443, 无本地MQTT |
| Mini Program 解包 | 提取微信小程序 wxapkg 包 | ❌ 未进行 |
| 固件分析 | 提取设备 OTA 固件分析 MQTT/CoAP 协议 | ❌ 未进行 |
| BLE 嗅探 | 本地蓝牙通信协议分析 | ❌ 未进行 |

---

## 2. API 架构概览

### 2.1 平台信息

| 信息 | 值 |
|------|------|
| **API 基础地址** | `https://saas.keyoo.com/app-api/v2.0` |
| **IoT 平台** | 企悠科技 Keyoo SaaS 物联网平台 |
| **通信协议** | HTTP REST（JSON over HTTPS） |
| **认证方式** | Bearer token（accessToken）+ MD5 请求签名 |
| **设备通信** | 云端轮询（Cloud Polling），设备端主动上报到云端 |

### 2.2 URL 端点

| 端点 | 路径 | 用途 |
|------|------|------|
| **Token 刷新** | `/login/spLogin/refreshToken` | 用 refreshToken 换取 accessToken |
| **获取设备列表** | `/sp/device/getSpDeviceList` | 获取用户绑定的所有设备 |
| **读取属性** | `/device/property/get` | 查询设备当前所有属性状态 |
| **设置属性** | `/device/property/set2` | 设置设备属性（开关、电机模式等） |
| **服务调用** | `/device/service/invoke2` | 调用设备特定服务（调光等） |
| **在线状态** | `/device/synOnlineStatus` | 查询设备在线状态 |

---

## 3. 认证协议

### 3.1 Token 体系

```
refreshToken (长期有效) ──→ accessToken (30天有效) ──→ API 调用
                                    │
                           Bearer Token 形式
                          "bearer eyJhbGciOi..."
```

### 3.2 Token 刷新流程

```http
POST https://saas.keyoo.com/app-api/v2.0/login/spLogin/refreshToken
Content-Type: application/json

{
    "refreshToken": "xxx",
    "appKey": "miniapp-hotata-prod",
    "appVersion": "miniapp_4.4.5.1",
    "timestamp": 1719201600000,
    "traceId": "refresh_1719201600000",
    "sysVersion": "Windows 10 x64",
    "phoneModel": "microsoft",
    "imei": "Windows 10 x64_w4.1.7.33_s3.14.3",
    "sign": "md5hash..."
}
```

响应：
```json
{
  "code": "000",
  "message": "success",
  "data": {
    "accessToken": "eyJhbGciOi...",
    "refreshToken": "newRefreshTokenHere",
    "tokenType": "bearer",
    "expiresIn": 2591999,
    "userId": "xxx"
  }
}
```

### 3.3 固定参数

| 参数 | 值 | 说明 |
|------|------|------|
| APP_KEY | `miniapp-hotata-prod` | 小程序应用标识 |
| APP_SECRET | `B322B40A-DBD2-26A2-F935-6E760917CB73` | 签名密钥 |
| APP_VERSION | `miniapp_4.4.5.1` | 小程序版本号 |
| IMEI | `Windows 10 x64_w4.1.7.33_s3.14.3` | 设备标识（PC抓包遗留） |
| PHONE_MODEL | `microsoft` | 设备型号 |
| SYS_VERSION | `Windows 10 x64` | 系统版本 |

> ⚠️ `APP_SECRET` 嵌入在小程序前端代码中，通过 Mini Program 解包可以定位到的硬编码字符串。

---

## 4. 签名算法

### 4.1 MD5 签名

所有请求（包括 Token 刷新）都需要 `sign` 字段。

生成步骤：
1. 复制 payload，移除 `sign` 字段
2. 按 key 字母序排序
3. 过滤掉值为 `None`、`""`、`dict`、`list` 的字段
4. 拼接为 `key1=value1&key2=value2` 格式
5. 末尾追加 `APP_SECRET`
6. 计算 MD5 得到签名字符串

### 4.2 实现示例（Python）

```python
import hashlib

def generate_sign(payload: dict, app_secret: str) -> str:
    p = {k: v for k, v in payload.items() if k != "sign"}
    arr = []
    for k in sorted(p.keys()):
        v = p[k]
        if v is None or v == "" or isinstance(v, (dict, list)):
            continue
        arr.append(f"{k}={v}")
    raw = "&".join(arr) + app_secret
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
```

---

## 5. API 端点详解

### 5.1 通用请求结构

每个请求包含：
- 通用 payload 头（`userid`、`iotId`、`appKey`、`timestamp`、`traceId`、`sysVersion`、`phoneModel`、`imei`）
- 签名 `sign`
- HTTP Header `authorization: bearer <accessToken>`

### 5.2 获取设备列表

```http
POST https://saas.keyoo.com/app-api/v2.0/sp/device/getSpDeviceList
```

响应 `data` 示例：
```json
{
  "data": [
    {
      "iotId": "a1b2c3d4e5f6",
      "deviceName": "智能晾衣机",
      "iotid": "a1b2c3d4e5f6",
      "productKey": "...",
      "deviceSecret": "...",
      "onlineStatus": 1
    }
  ]
}
```

### 5.3 读取设备属性

```http
POST https://saas.keyoo.com/app-api/v2.0/device/property/get
```

响应 `data` 格式（数组式属性列表）：
```json
{
  "code": "000",
  "data": [
    {"attribute": "Position", "value": 50, "time": 1719201600000},
    {"attribute": "LightSwitch", "value": 1, "time": 1719201600000},
    {"attribute": "DryingSwitch", "value": 0, "time": 1719201600000},
    {"attribute": "AirDryingSwitch", "value": 0, "time": 1719201600000},
    {"attribute": "DisinfectionSwitch", "value": 0, "time": 1719201600000},
    {"attribute": "IonsSwitch", "value": 0, "time": 1719201600000},
    {"attribute": "LightBrightness", "value": 80, "time": 1719201600000},
    {"attribute": "MotorControlMode", "value": 0, "time": 1719201600000},
    {"attribute": "LightRemainingTime", "value": 0, "time": 1719201600000},
    {"attribute": "DryingRemainingTime", "value": 0, "time": 1719201600000},
    {"attribute": "AirDryingRemainingTime", "value": 0, "time": 1719201600000},
    {"attribute": "IonsRemainingTime", "value": 0, "time": 1719201600000},
    {"attribute": "DisinfectionRemainingTime", "value": 0, "time": 1719201600000}
  ]
}
```

### 5.4 设置设备属性

```http
POST https://saas.keyoo.com/app-api/v2.0/device/property/set2
```

特殊参数：`paramJson` — JSON 字符串化后的属性键值对。

```json
{
  "paramJson": "{\"MotorControlMode\": 2}"
}
```

### 5.5 调用设备服务

```http
POST https://saas.keyoo.com/app-api/v2.0/device/service/invoke2
```

额外参数：`serviceName` + `paramJson`

```json
{
  "serviceName": "LightBrightnessControl",
  "paramJson": "{\"Brightness\": 80}"
}
```

### 5.6 在线状态查询

```http
POST https://saas.keyoo.com/app-api/v2.0/device/synOnlineStatus
```

---

## 6. 设备属性图谱

### 6.1 完整属性列表

| 属性名 | 类型 | 取值范围 | 说明 |
|--------|------|---------|------|
| `Position` | int | 0-100 | 晾衣杆位置：0=完全下降，100=完全收回 |
| `PowerSwitch` | bool | 0/1 | 总电源开关 |
| `LightSwitch` | bool | 0/1 | 照明开关 |
| `DryingSwitch` | bool | 0/1 | 烘干开关 |
| `AirDryingSwitch` | bool | 0/1 | 风干开关 |
| `DisinfectionSwitch` | bool | 0/1 | 消毒/紫外灯开关 |
| `IonsSwitch` | bool | 0/1 | 负离子开关 |
| `LightBrightness` | int | 1-100 | 灯光亮度百分比 |
| `MotorControlMode` | int | 0/1/2 | 电机模式：0=停止，1=上升，2=下降 |
| `LightRemainingTime` | int | 0-N | 照明定时剩余分钟数 |
| `DryingRemainingTime` | int | 0-N | 烘干定时剩余分钟数 |
| `AirDryingRemainingTime` | int | 0-N | 风干定时剩余分钟数 |
| `DisinfectionRemainingTime` | int | 0-N | 消毒定时剩余分钟数 |
| `IonsRemainingTime` | int | 0-N | 负离子定时剩余分钟数 |

### 6.2 属性映射到 HA 实体

| HA 平台 | 实体 | 关联 API 属性 |
|---------|------|-------------|
| binary_sensor | 在线状态 | ~（来自 online status API） |
| binary_sensor | 电源状态 | `PowerSwitch` |
| cover | 晾衣机 | `MotorControlMode`（控制）；`Position`（反馈） |
| light | 照明 | `LightSwitch` + `LightBrightness` |
| switch | 电源 | `PowerSwitch` |
| switch | 烘干 | `DryingSwitch` |
| switch | 风干 | `AirDryingSwitch` |
| switch | 消毒 | `DisinfectionSwitch` |
| switch | 负离子 | `IonsSwitch` |
| sensor | 位置 | `Position` |
| sensor | 照明定时 | `LightRemainingTime` |
| sensor | 烘干定时 | `DryingRemainingTime` |
| sensor | 风干定时 | `AirDryingRemainingTime` |
| sensor | 消毒定时 | `DisinfectionRemainingTime` |
| sensor | 负离子定时 | `IonsRemainingTime` |
| sensor | 电机模式 | `MotorControlMode` |
| number | 最低位置设置 | 本地配置，非 API 属性 |

---

## 7. 控制命令

### 7.1 电机控制

通过 `property/set2` 设置 `MotorControlMode`：

| 命令 | MotorControlMode 值 |
|------|--------------------|
| 上升（收回） | `1` |
| 下降（展开） | `2` |
| 停止 | `0` |

> ⚠️ 设备本身有硬件限位保护。下降到最低时自动停止。

### 7.2 开关控制

所有开关通过 `property/set2` 设置：

```json
{"LightSwitch": 1}    // 开灯
{"LightSwitch": 0}    // 关灯
{"DryingSwitch": 1}   // 开烘干
{"DryingSwitch": 0}   // 关烘干
{"AirDryingSwitch": 1} // 开风干
{"IonsSwitch": 1}     // 开负离子
{"DisinfectionSwitch": 1} // 开启消毒
{"PowerSwitch": 1}    // 开电源
```

### 7.3 亮度控制

通过 `service/invoke2` 调用特定服务：

```json
{
  "serviceName": "LightBrightnessControl",
  "paramJson": "{\"Brightness\": 80}"
}
```

`Brightness` 范围：1-100。此命令需要先开灯（`LightSwitch=1`）才有效。

---

## 8. 完整数据流

```
                微信小程序 / Android App
                        │
                        ▼
              ┌─────────────────────┐
              │  MD5 签名客户端请求   │
              │  Bearer Token 认证   │
              └────────┬────────────┘
                       │ HTTPS
                       ▼
              ┌─────────────────────┐
              │   saas.keyoo.com    │
              │  企悠科技 IoT 平台   │
              └────────┬────────────┘
                       │ IoT Gateway
                       ▼
              ┌─────────────────────┐
              │   设备 Cloud API    │
              │  (property/set/get) │
              └────────┬────────────┘
                       │ MQTT/私有TCP
                       ▼
              ┌─────────────────────┐
              │   好太太智能晾衣机    │
              │   (ESP32/模组通信)   │
              └─────────────────────┘
```

### 8.1 控制流程

```
用户操作 → HA 前端 → Cover/Switch/Light Entity
                          │
                    hub.control_cover("down")
                          │
                    _property_set({"MotorControlMode": 2})
                          │
                    POST https://saas.keyoo.com/.../property/set2
                          │
                    Check code == "000" → 发送成功
                          │
                    轮询更新 → property/get 获取最新状态
                          │
                    变化检测（hash）→ 通知 listener → 更新 HA 实体
```

### 8.2 轮询策略

| 参数 | 值 |
|------|------|
| 状态轮询间隔 | 5 秒 |
| Token 刷新条件 | 过期前 2 分钟 / 收到 401 时立即刷新 |
| 预防性 Token 刷新 | 每 6 小时一次 |
| Token 过期时间 | 30天（2591999 秒） |

---

## 9. HA 集成架构

### 9.1 文件结构

```
custom_components/hotata_airer/
├── __init__.py          # 集成入口，启动轮询
├── const.py             # 常量：API URL、固定参数
├── config_flow.py       # UI 配置流（仅需 refreshToken）
├── hub.py               # 核心：API 通信、签名、状态解析、Token 管理
├── cover.py             # Cover 平台（升降控制 + 自动停止）
├── light.py             # Light 平台（开关 + 亮度）
├── switch.py            # Switch 平台（电源/烘干/风干/消毒/负离子）
├── sensor.py            # Sensor 平台（位置/5个定时器/电机模式）
├── binary_sensor.py     # Binary Sensor（在线状态/电源状态）
├── number.py            # Number 平台（最低位置设置）
├── diagnostics.py       # HA 诊断信息
├── manifest.json
├── strings.json
├── translations/
│   ├── en.json
│   └── zh-Hans.json
└── brand/
    ├── icon.png
    └── logo.png
```

### 9.2 反向依赖图

```
__init__.py
    └── HotataHub (hub.py) ← 核心类
         ├── binary_sensor.py → OnlineSensor, PowerSensor
         ├── cover.py         → HotataCover
         ├── light.py         → HotataLight
         ├── switch.py        → HotataSwitch (×5)
         ├── sensor.py        → PositionSensor, RemainingTimeSensor (×5), MotorControlModeSensor
         └── number.py        → DescentTimeNumber
```

---

## 10. APK 逆向分析

### 10.1 APK 基本信息

| 项目 | 值 |
|------|------|
| **包名** | `com.hotata.keyoolot` |
| **版本** | v3.5.8 |
| **大小** | 105 MB |
| **加固方式** | DVMProtect / 360 加固 |
| **MD5** | `B65DE68FB58266FB4D6DA35B67623BE7` |
| **框架** | React Native（含 Hermes JS 引擎） |
| **来源** | downkuai.com |

### 10.2 反编译结果

Jadx 反编译发现 APK 被 **360 加固/DVMProtect** 保护。assets 中有一个 `libjiagu_a64.so` (1.1 MB) 加固壳。反编译仅得到 6 个 Java 壳类和空壳 Application，实际业务逻辑全部在 native .so 库中。

**Java 壳文件（6个）:**
- `com.stub.StubApp` — 入口壳
- `com.stub.StubAppProvider` — ContentProvider 壳
- `com.stub.StubAppProxy` — Proxy Activity 壳
- `com.stub.StubAppReceiver` — BroadcastReceiver 壳
- `com.stub.StubAppService` — Service 壳
- 加固后的空 `Application` 类

### 10.3 Native 库完整列表

| 库名 | 大小 | 用途推测 |
|------|------|---------|
| `libv8android.so` | 21.6 MB | V8 JavaScript 引擎（React Native Hermes 复用） |
| `libServerInterface.so` | 11.8 MB | **API 通信核心** — 含 FFmpeg + JSON + 加密 + RTSP/RTMP 网络栈 |
| `libiot_video_demo.so` | 5.6 MB | 阿里云 IoT 视频 SDK |
| `libijkffmpeg.so` | 5.6 MB | ijkplayer FFmpeg（视频播放） |
| `liblvmedia.so` | 4.9 MB | 乐橙云 AI 摄像头媒体处理 |
| `libiotcommon.so` | 4.2 MB | **阿里云 IoT 公共库** — OpenSSL AES/DES/BF/SM4 全套加密 |
| `libGVoiceUtils.so` | 2.3 MB | 腾讯 GVoice（语音通信） |
| `libIVIEWSAVAPIs.so` | 2.3 MB | 中维世纪音视频 API（摄像头） |
| `libmygvoice.so` | 2.4 MB | 腾讯 GVoice 增强 |
| `libcrypto.1.1.so` | 2.1 MB | OpenSSL 1.1 加密库 |
| `libcurl.so` | 2.0 MB | libcurl HTTP 库 |
| `liblvffmpeg.so` | 3.3 MB | 乐橙 FFmpeg |
| `libjutils.so` | 1.6 MB | JNI 工具类 |
| `libiotqjs.so` | 1.0 MB | 阿里云 IoT QuickJS |
| `libcoap.so` | 0.9 MB | **CoAP 协议栈**（局域网设备发现） |
| `libiot-soundtouch.so` | 0.9 MB | 阿里云 IoT 音频处理 |
| `libsoundtouch.so` | 0.9 MB | 音频处理（SoundTouch 库） |
| `libiconv.so` | 0.9 MB | 字符编码转换 |
| `libreactnativejni.so` | 0.8 MB | React Native JNI 桥接 |
| `libiotmgr.so` | 0.7 MB | 阿里云 IoT 管理器 |
| `libJavaToC.so` | 0.6 MB | Java ↔ C 桥接（含 GCC 编译错误字符串） |
| `libtnet-3.1.14.so` | 0.4 MB | 腾讯 Tnet 网络库 |
| `libssl.1.1.so` | 0.4 MB | OpenSSL 1.1 TLS |
| `libitls.so` | 0.3 MB | **阿里云 IoT TLS/mbedTLS 替代实现** |
| `libyoga.so` | 0.2 MB | React Native Yoga 布局引擎 |
| `libfb.so` | 0.2 MB | Facebook Folly 基础库 |
| `libfolly_json.so` | 0.3 MB | Facebook Folly JSON |
| `libimagepipeline.so` | 0.4 MB | React Native 图片管道 |
| `libpns-2.13.3-LogOnlineStandardCuumRelease_alijtca_plus.so` | 0.4 MB | 阿里云推送通知服务 |
| `libxnet-android.so` | 0.2 MB | 腾讯 XNet 网络库 |
| `libmedia-server.so` | 0.3 MB | 媒体服务器 |
| `libandroid_id2.so` | 0.2 MB | Android 设备 ID 获取 |
| `liblvrtmp.so` | 0.08 MB | 乐橙 RTMP |
| `libIVIEWSP2P.so` | 0.06 MB | 中维世纪 P2P |
| `libIVIEWSLANUDP.so` | 0.03 MB | 中维世纪 LAN UDP |
| `libzbar.so` | 0.2 MB | ZBar 二维码扫描 |
| `libBugly.so` | 0.2 MB | 腾讯 Bugly 崩溃收集 |
| `libBugly-ext.so` | 0.2 MB | 腾讯 Bugly 扩展 |

### 10.4 libServerInterface.so 关键发现（11.8 MB）

这是 **最核心的库**，负责所有 API 通信。通过 strings 分析发现：

**FFmpeg 解码器:**
- 大量 `ff_*_decoder` 符号：h264, mpeg4, aac, mp3, vp8, vp9, flv, h263, hevc, mjpeg 等
- FFmpeg 2.8.15 版本（交叉编译参数可见）
- 编译目标: `aarch64-linux-android`, API 21（Android 5.0+）

**JSON 处理:**
- 完整的 JSON 解析库（`json_parse_document`, `json_escape`, `json_free_value` 等）
- 自定义 JSON 序列化/反序列化

**加密算法:**
- **av_aes_*** — FFmpeg AES 加解密（init, crypt, alloc）
- **av_md5_*** — FFmpeg MD5 哈希
- **av_des_*** — FFmpeg DES 加解密（含 MAC 验证）
- **av_hmac_*** — FFmpeg HMAC（init, update, final, calc）
- **av_sha_*** — FFmpeg SHA-1/224/256/384/512
- **av_base64_*** — Base64 编解码

> ⚠️ libServerInterface.so 中的加密函数基于 FFmpeg（av_*），而非 OpenSSL。这与当前集成使用 MD5 签名一致。

**JNI 接口（Lancens 系列）:**
```
Java_com_lancens_Lancensapp_JNIInterface_connectDevide
Java_com_lancens_Lancensapp_JNIInterface_getDeviceUID
Java_com_lancens_Lancensapp_JNIInterface_getSearchedDevicesNumber
Java_com_lancens_Lancensapp_JNIInterface_searchDevice
Java_com_lancens_Lancensapp_JNIInterface_setApInfo
Java_com_lancens_Lancensapp_JNIInterface_setDevice
Java_com_lancens_Lancensapp_JNIInterface_stopConnectDevide
```

> **Lancens = 蓝橙/乐橙**（中维世纪旗下摄像头方案）。表明好太太 App 集成了乐橙的摄像头/视频能力。

**视频/音频传输:**
- RTMP 协议栈完整（RTMP Handshake, FCPublish/FCSubscribe, connect/publish/subscribe）
- RTSP 协议栈（DESCRIBE, SETUP, ANNOUNCE, RTP over UDP/TCP）
- HLS 协议（`#EXT-X-KEY:METHOD=AES-128`）
- MQTT 远程控制（`onFCPublish`, `sendMotor`, `sendMotorState`, `sendRequestState`, `sendRequestTimerRecord`）
- UDP P2P TCP 传输（`startUdpServer`, `connectPushServer`, `tcpConnectServer`, `tcpConnectThreadServer`）

**JSON 命令格式（设备文件传输 API）：**
```json
{"cmd":"request_delete_file","verification":"%s/%s","file_name":"%s"}
{"cmd":"request_download_file","verification":"%s/%s","file_name":"%s"}
{"cmd":"request_get_file_list","verification":"%s/%s"}
{"cmd":"request_get_file_number","verification":"%s/%s"}
```

### 10.5 libiotcommon.so 关键发现（4.2 MB）

**阿里云 IoT 核心库。** 包含全套 OpenSSL 加密：

**对称加密:**
- AES-128/192/256 CBC, CFB, CFB1, CFB8, CTR, ECB, OFB
- DES/EDE3 CBC, CFB, CFB1, CFB8, ECB, OFB
- Blowfish, CAST5, IDEA, SEED, SM4 的 CBC/CFB/ECB/OFB 模式

**哈希/签名:**
- MD4, MD5, RIPEMD160, SHA1/224/256/384/512
- HMAC 各种算法
- EVP 高级加密接口全量

**阿里云 IoT 特定 JNI:**
```
Java_com_aliyun_iotx_iot_common_IoTCommon_native_*
```

**其他关键发现:**
- `SharePHelper` — 阿里云设备配网辅助工具
- OpenSSL ENGINE 接口
- SSL/TLS 密码套件排序函数
- 各种 Base64/BIO 函数

### 10.6 libitls.so 关键发现（0.3 MB）

**阿里云 IoT TLS 替代实现（mbedTLS 风格）:**

```
ali_aes_setkey_enc/dec, ali_aes_crypt_ecb/cbc/ctr...
ali_algo_aes_cbc_encrypt/decrypt
ali_algo_rsa_sign_verify
ali_algo_hmac_sha256
km_asym_encrypt, km_cipher
ssl_encrypt_buf, ssl_change_cipher_spec
ciphersuite 密码套件协商
```

- 大量 `ali_algo_*`、`ali_aes_*` 函数 — 阿里魔改的 AES 算法
- `km_*` 密钥管理函数（km_asym_encrypt, km_cipher, km_init, km_deinit）
- mbedTLS 的 SSL 实现：握手、密码套件、加密、变更密码规格

### 10.7 libiotapiclient.so 关键发现（0.05 MB）

```
Java_com_aliyun_iotx_linkvisual_*
/vision/customer/sls/token/query
```

**阿里云 LinkVisual** 视频 API 客户端 JNI 接口和 API 路径。表明 App 集成了阿里云 IoT 视频能力（摄像头设备预览）。

### 10.8 配网配置（assets/config.conf）

完整的阿里云 IoT 配网策略：

```json
{
  "configStrategy": [
    "SoftAPConfigStrategy",
    "BreezeConfigStrategy" (BLE 蓝牙),
    ...
  ],
  "deviceDiscovery": [
    "CoAPDiscoverChain",
    "CloudDiscoverChain",
    "BreezeDiscoverChain",
    "BleMeshDiscoverChain",
    "SoftAPDiscoverChain",
    ...
  ]
}
```

**支持配网方式：**
1. **SoftAP** — 设备发 Wi-Fi 热点，手机连入配置
2. **BLE Breeze** — 蓝牙低功耗配网
3. **广播/ZeroConfig** — 局域网广播
4. **App/BLE Mesh** — 蓝牙 Mesh 组网
5. **二维码** — 扫码配网
6. **声波** — 天猫精灵声波配网
7. **云端静默** — 已联网设备静默激活

**设备发现链：**
1. **CoAP** — 局域网 CoAP 发现
2. **云端** — 云端设备列表
3. **BLE** — 蓝牙发现
4. **蓝牙 Mesh** — 蓝牙 Mesh 发现
5. **SoftAP** — 配置模式 AP 发现

### 10.9 APK assets 资源汇总

| 资产 | 说明 |
|------|------|
| `dse_v1_239-119-oneref-e.nn` (3.2 MB) | React Native Hermes 字节码 Bundle — 未直接找到 keyoo/saas 字符串，逻辑在 native .so 中 |
| `libjiagu_a64.so` (1.1 MB) | 360 加固壳 |
| `hmsrootcas.bks` (34 KB) | 华为移动服务根证书 |
| `grs_sp.bks` / `grs_sdk_*` 系列配置 | 华为 GRS（全球路由服务）SDK |
| `china_city_data.json` | 城市数据（天气/地区选择） |
| `sdk_fw_countries/*.json` | 国际化翻译文件（多语言字符串） |
| 大量 Lottie JSON | UI 动画（配网/开关/升降动画） |
| 大量 `.png` / `.jpg` | UI 配图 |

### 10.10 APK 总体架构

```
┌─────────────────────────────────────────────────────┐
│                  360 加固壳（libjiagu）              │
│         Java Stub (StubApp, 6个壳类)                │
├─────────────────────────────────────────────────────┤
│                    React Native                     │
│              Hermes JS Bundle (3.2MB)               │
│      ⊗ JS Bundle 被加固阻挡，未恢复源码              │
├─────────────┬───────────┬───────────┬───────────────┤
│  Aliyun IoT │  Lancens  │    Tencent│   FFmpeg/ijk  │
│  libiotmgr  │  video P2P│  GVoice   │  播放引擎     │
│  libiotcom  │  IVIEWS*  │  Bugly    │               │
│  libitls    │  libtnet  │  Tnet     │               │
│  libcoap    │  libxnet  │           │               │
│             │           │           │               │
├─────────────┴───────────┴───────────┴───────────────┤
│               Android SDK / JNI                      │
└─────────────────────────────────────────────────────┘
```

### 10.11 HA 端网络观测

在 HA 服务器用 tcpdump 观测到：

- HA 通过 **HTTPS** 直连 `saas.keyoo.com:443` — 云端 REST API
- **无本地 MQTT** — 没有发现向局域网 IP 的 MQTT 连接
- 设备到云端走**私有 TCP 协议**（非标准 MQTT/HTTP）
- HA 配置只有本地 `descent_time` 参数

---

## 11. 进一步可探索方向

### 11.1 高优先级

| 方向 | 预期收益 | 方法 |
|------|---------|------|
| **本地 MQTT 协议** | 无需云端轮询（低延迟、离线可用） | 分析设备局域网通信（Wi-Fi/MQTT） |
| **设备 OTA 固件** | 了解完整指令集 | 抓取固件下载链接，binwalk 分析 |
| **更多 service 命令** | 发现未暴露功能（如定时设置、蜂鸣器） | 抓取小程序所有交互，枚举 serviceName |
| **libServerInterface.so 深度逆向** | 获取 MQTT 凭据、局域网协议 | Ghidra 反编译，查找 secret/key |

### 11.2 中优先级

| 方向 | 预期收益 |
|------|---------|
| 微信小程序 wxapkg 解包 | 获取完整前端逻辑、未公开 API、APP_SECRET 来源 |
| 第三方云 API 挖掘 | 发现场景联动、设备分享、用户管理 API |
| 阿里云 IoT 设备通信协议 | 直接通过阿里云 IoT 平台控制（低延迟） |
| APK 脱壳修复 | 使用 Frida/unpacker 脱壳后重新 Jadx，获取 RN Bundle 源码 |

### 11.3 低优先级

| 方向 | 说明 |
|------|------|
| BLE 本地协议 | 好太太晾衣架可能也支持蓝牙遥控器（非 Wi-Fi 版本） |
| Zigbee 网关协议 | 需要接入好太太 Zigbee 网关才能分析 |
| 历史数据 API | 能耗统计、使用时长等 |

### 11.4 已知未实现的 API 领域

通过分析 API 路径结构，可能存在的未探索端点：
- `/app-api/v2.0/sp/device/scene/` — 场景管理
- `/app-api/v2.0/sp/device/timer/` — 定时任务
- `/app-api/v2.0/sp/device/ota/` — 固件升级
- `/app-api/v2.0/sp/device/sharing/` — 设备分享
- `/app-api/v2.0/message/` — 消息推送

### 11.5 APK 脱壳策略（进阶逆向）

| 方法 | 工具 | 难度 |
|------|------|------|
| Frida 运行时脱壳 | frida-dump, frida-dexdump | 中 |
| 内存 dump 后修复 | dump-dex + dexfixer | 中高 |
| 360 加固专用脱壳 | 360-unpacker | 高 |
| 多开/分身绕过加固 | VMOS Pro / 平行空间 | 低，但可能不完整 |

---

## 附录

### A. 关键发现时间线

| 日期 | 事件 |
|------|------|
| 2026-04-23 | v1.1.0 — 初始 API 逆向，基本信息获取 |
| 2026-04-24 | v2.1.0 — 完整功能覆盖：所有 switch/light/sensor 映射 |
| 2026-04-25 | Token 刷新修复，使用 cURL 比对修正 payload |
| 2026-06-17 | 多设备支持，cover 自动停止功能 |
| 2026-06-22 | Beta 发布准备 |
| 2026-06-23 | 智能定时器剩余时间修复（API 直接返回分钟） |
| 2026-06-24 | v2.2.0-beta — 当前最新版本 |
| 2026-06-25 | APK 完整逆向：360加固 RN 应用，5 核心 .so 分析 |

### B. APK 关键目录结构

```
D:\ai-hub\apk\
├── hotata_keyoolot.apk              # 原始 APK (105 MB)
├── unzip/                           # 解压后完整目录
├── extracted/                       # 提取的资产和配置文件
├── jadx_out/                        # Jadx 反编译输出 (6336 文件，6个Java壳)
└── libs/                            # 提取的 arm64-v8a 库
    ├── libServerInterface.so        # 11.8 MB — API+加密+视频网络栈
    ├── libiotcommon.so              # 4.2 MB — 阿里云 IoT + OpenSSL
    ├── libitls.so                   # 0.3 MB — 阿里云 IoT TLS
    ├── libJavaToC.so                # 0.6 MB — Java <-> C 桥接
    └── libiotapiclient.so           # 0.05 MB — 阿里云 LinkVisual API
```

### C. 安全注意事项

- `APP_SECRET` 是前端硬编码，可通过解包获取
- 仅使用 refreshToken 即可完全控制设备
- 建议在 HA 中安全存储 Token，不要公开分享
- 该集成使用 CC BY-NC 4.0 许可，仅限个人非商业使用
- APK 的 keyoo 通信逻辑在加固的 native .so 中，未直接泄露 APP_SECRET

### D. 本地网络拓扑（HA 服务器观察）

| 源 | 目标 | 协议 | 端口 | 用途 |
|----|------|------|------|------|
| HA Server | saas.keyoo.com | HTTPS | 443 | Keyoo 云 API |
| 设备 (Wi-Fi) | saas.keyoo.com | 私有 TCP | 未知 | 设备上报到云端 |
| 设备 (Wi-Fi) | 未发现 | MQTT | 1883/8883 | ❌ 本地无 MQTT |
| HA Server | 局域网 | ARP | N/A | 无本地 CoAP/UDP 发现 |
