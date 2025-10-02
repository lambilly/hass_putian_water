# 莆田水费 Home Assistant 集成

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

这是一个用于 Home Assistant 的自定义集成，用于查询莆田水务的水费余额和账单信息。

## 功能特性

- 🔐 支持 Token 和 Cookie 认证
- 💰 显示水费余额信息
- 📊 显示上月水费账单详情
- ⏰ 自动每日更新数据
- 🏠 在 Home Assistant 中创建传感器实体

## 安装

### 方法一：通过 HACS（推荐）

1. 确保已安装 [HACS](https://hacs.xyz/)
2. 在 HACS 中添加自定义仓库：
   - 仓库：`lambilly/putian_water`
   - 类别：集成
3. 搜索并安装 "莆田水费"
4. 重启 Home Assistant

### 方法二：手动安装

1. 将 `custom_components/putian_water` 文件夹复制到你的 Home Assistant 的 `custom_components` 目录
2. 重启 Home Assistant
3. 在集成页面添加 "莆田水费"

## 配置

### 获取认证信息

1. 访问 [莆田水务网站](https://wt.ptswater.cn/)
2. 登录你的账户
3. 打开浏览器开发者工具（F12）
4. 找到水费查询的请求，复制以下信息：
   - **Token**: 在请求体中的 `token` 字段
   - **Cookie**: 在请求头中的 `Cookie` 字段

### 添加集成

1. 进入 Home Assistant → 设置 → 设备与服务
2. 点击 "添加集成"
3. 搜索 "莆田水费"
4. 填写以下信息：
   - **水表号码**: 你的水表号
   - **认证令牌 (Token)**: 从网站获取的 Token
   - **会话 Cookie**: 从网站获取的 Cookie
   - **查询年份**: 要查询的年份（默认当前年份）
   - **水务公司 ID**: 默认为 3
   - **区域 ID**: 默认为 0

## 创建的实体

集成会创建以下传感器实体：

### 水费余额传感器
- **实体ID**: `sensor.water_balance`
- **状态**: 当前账户余额
- **属性**:
  - 水表号码
  - 用户地址
  - 用户状态
  - 欠费金额
  - 上次读数日期
  - 上次读数
  - 当前用水量

### 上月水费传感器
- **实体ID**: `sensor.last_water_bill`
- **状态**: 上月水费金额
- **属性**:
  - 账单周期
  - 用户地址
  - 用户姓名
  - 用户编号
  - 水表号码
  - 上次读数
  - 本次读数
  - 用水量
  - 缴费状态
  - 缴费日期

## 自动化示例

```yaml
# 当水费余额低于阈值时发送通知
automation:
  - alias: "水费余额提醒"
    trigger:
      - platform: numeric_state
        entity_id: sensor.water_balance
        below: 50
    action:
      - service: notify.mobile_app
        data:
          message: "水费余额不足，请及时充值！当前余额：{{ states('sensor.water_balance') }}元"

# 每月1日查询水费账单
automation:
  - alias: "每月水费查询"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      - condition: time
        day: 1
    action:
      - service: homeassistant.update_entity
        target:
          entity_id:
            - sensor.water_balance
            - sensor.last_water_bill
