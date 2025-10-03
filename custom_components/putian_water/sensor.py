"""莆田水费传感器."""
from __future__ import annotations

import logging
from datetime import timedelta, datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置传感器平台."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    
    coordinator = PutianWaterCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    sensors = [
        PutianWaterBalanceSensor(coordinator, entry),
        PutianWaterLastBillSensor(coordinator, entry),
        PutianWaterUpdateTimeSensor(coordinator, entry),
    ]
    
    async_add_entities(sensors)


class PutianWaterCoordinator(DataUpdateCoordinator):
    """莆田水费数据协调器."""
    
    def __init__(self, hass: HomeAssistant, api):
        """初始化协调器."""
        super().__init__(
            hass,
            _LOGGER,
            name="莆田水费",
            update_interval=timedelta(hours=24),  # 24小时更新一次
        )
        self.api = api
    
    async def _async_update_data(self):
        """获取最新数据."""
        try:
            balance_data = await self.api.get_user_meter_list()
            bill_data = await self.api.get_payment_info()
            
            # 使用正确的方法获取当前时间
            current_time = dt_util.now()
            
            return {
                "balance": self._process_balance_data(balance_data),
                "bill": self._process_bill_data(bill_data),
                "query_year": self.api._query_year,
                "last_update": current_time
            }
        except Exception as ex:
            _LOGGER.error("更新水费数据失败: %s", ex)
            # 返回空数据而不是抛出异常，避免传感器不可用
            current_time = dt_util.now()
            return {
                "balance": {},
                "bill": {},
                "query_year": self.api._query_year,
                "last_update": current_time,
                "error": str(ex)
            }
    
    def _process_balance_data(self, data):
        """处理余额数据."""
        if not data or not data.get("data") or not isinstance(data["data"], list) or len(data["data"]) == 0:
            _LOGGER.warning("No balance data available")
            return {}
            
        meter = data["data"][0]
        return {
            "user": {
                "meter_number": meter.get("meterNumber", ""),
                "meter_name": meter.get("meterName", ""),
                "meter_address": meter.get("meterAddress", ""),
                "meter_mobile": meter.get("meterMobile", ""),
            },
            "account": {
                "user_status": meter.get("userStatus", ""),
                "balance": float(meter.get("balance", 0)) if meter.get("balance") else 0.0,
                "arrearage": float(meter.get("arrearage", 0)) if meter.get("arrearage") else 0.0,
                "unit": "元",
            },
            "meter": {
                "last_read_date": meter.get("lastreaddate", ""),
                "last_read_value": meter.get("lastto", ""),
                "next_read_date": meter.get("nextreaddate", ""),
                "next_read_value": meter.get("nextto", ""),
                "current_usage": float(meter.get("consumedVolume", 0)) if meter.get("consumedVolume") else 0.0,
                "unit": "吨",
            }
        }
    
    def _process_bill_data(self, data):
        """处理账单数据."""
        if not data or not data.get("data") or not isinstance(data["data"], list) or len(data["data"]) == 0:
            _LOGGER.warning("No bill data available")
            return {}
            
        bill = data["data"][0]
        return {
            "period": bill.get("costDate", "无数据"),
            "address": bill.get("address", "无数据"),
            "user_name": bill.get("cardname", "无数据"),
            "user_code": bill.get("cardno", "无数据"),
            "meter_number": bill.get("meternumber", "无数据"),
            "data_reading": {
                "last_read_value": bill.get("lastRead", "0"),
                "last_read_date": bill.get("lastMetertime", "无日期"),
                "current_read_value": bill.get("currentRead", "0"),
                "current_read_date": bill.get("metertime", "无日期"),
                "volume": float(bill.get("consumedVolume", 0)) if bill.get("consumedVolume") else 0.0,
                "price_detail": bill.get("price1", "无价格信息")
            },
            "payment": {
                "amount": float(bill.get("payablePrincipal", 0)) if bill.get("payablePrincipal") else 0.0,
                "status": bill.get("payStatus", "未知状态"),
                "date": bill.get("paymentDate", "").split(' ')[0] if bill.get("paymentDate") else "未缴费"
            }
        }


class PutianWaterSensor(CoordinatorEntity, SensorEntity):
    """莆田水费传感器基类."""
    
    def __init__(self, coordinator, entry, sensor_type):
        """初始化传感器."""
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_type = sensor_type
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "水费查询",
            "manufacturer": "莆田水务",
            "model": "水费查询设备",
            "configuration_url": "https://wt.ptswater.cn",
        }


class PutianWaterBalanceSensor(PutianWaterSensor):
    """水费余额传感器."""
    
    def __init__(self, coordinator, entry):
        """初始化余额传感器."""
        super().__init__(coordinator, entry, "balance")
        self._attr_name = "水费余额"
        self._attr_unique_id = f"{entry.entry_id}_balance"
        self._attr_icon = "mdi:currency-cny"
        self._attr_native_unit_of_measurement = "元"
    
    @property
    def native_value(self):
        """返回传感器值."""
        if (self.coordinator.data and 
            "balance" in self.coordinator.data and 
            "account" in self.coordinator.data["balance"]):
            return self.coordinator.data["balance"]["account"]["balance"]
        return None
    
    @property
    def extra_state_attributes(self):
        """返回传感器属性."""
        if (not self.coordinator.data or 
            "balance" not in self.coordinator.data or 
            not self.coordinator.data["balance"]):
            return {"error": "无数据"}
        
        data = self.coordinator.data["balance"]
        attrs = {
            "query_year": self.coordinator.data.get("query_year", ""),
            "last_update": self.coordinator.data["last_update"].isoformat() if self.coordinator.data.get("last_update") else "",
        }
        
        if "user" in data:
            attrs.update({
                "meter_number": data["user"].get("meter_number", ""),
                "meter_address": data["user"].get("meter_address", ""),
            })
        
        if "account" in data:
            attrs.update({
                "user_status": data["account"].get("user_status", ""),
                "arrearage": data["account"].get("arrearage", 0),
            })
            
        if "meter" in data:
            attrs.update({
                "last_read_date": data["meter"].get("last_read_date", ""),
                "last_read_value": data["meter"].get("last_read_value", ""),
                "current_usage": data["meter"].get("current_usage", 0),
            })
            
        if "error" in self.coordinator.data:
            attrs["error"] = self.coordinator.data["error"]
            
        return attrs


class PutianWaterLastBillSensor(PutianWaterSensor):
    """上月水费传感器."""
    
    def __init__(self, coordinator, entry):
        """初始化上月水费传感器."""
        super().__init__(coordinator, entry, "bill")
        self._attr_name = "上月水费"
        self._attr_unique_id = f"{entry.entry_id}_last_bill"
        self._attr_icon = "mdi:currency-cny"
        self._attr_native_unit_of_measurement = "元"
    
    @property
    def native_value(self):
        """返回传感器值."""
        if (self.coordinator.data and 
            "bill" in self.coordinator.data and 
            "payment" in self.coordinator.data["bill"]):
            return self.coordinator.data["bill"]["payment"]["amount"]
        return None
    
    @property
    def extra_state_attributes(self):
        """返回传感器属性."""
        if (not self.coordinator.data or 
            "bill" not in self.coordinator.data or 
            not self.coordinator.data["bill"]):
            return {"error": "无数据"}
        
        data = self.coordinator.data["bill"]
        attrs = {
            "query_year": self.coordinator.data.get("query_year", ""),
            "last_update": self.coordinator.data["last_update"].isoformat() if self.coordinator.data.get("last_update") else "",
        }
        
        # 添加基本信息
        attrs.update({
            "period": data.get("period", "无数据"),
            "address": data.get("address", "无数据"),
            "user_name": data.get("user_name", "无数据"),
            "user_code": data.get("user_code", "无数据"),
            "meter_number": data.get("meter_number", "无数据"),
        })
        
        # 添加读数信息
        if "data_reading" in data:
            reading = data["data_reading"]
            attrs.update({
                "last_read_value": reading.get("last_read_value", "0"),
                "last_read_date": reading.get("last_read_date", "无日期"),
                "current_read_value": reading.get("current_read_value", "0"),
                "current_read_date": reading.get("current_read_date", "无日期"),
                "volume": reading.get("volume", 0),
                "price_detail": reading.get("price_detail", "无价格信息"),
            })
        
        # 添加支付信息
        if "payment" in data:
            payment = data["payment"]
            attrs.update({
                "payment_status": payment.get("status", "未知状态"),
                "payment_date": payment.get("date", "未缴费"),
            })
            
        if "error" in self.coordinator.data:
            attrs["error"] = self.coordinator.data["error"]
            
        return attrs


class PutianWaterUpdateTimeSensor(PutianWaterSensor):
    """更新时间传感器."""
    
    def __init__(self, coordinator, entry):
        """初始化更新时间传感器."""
        super().__init__(coordinator, entry, "update_time")
        self._attr_name = "更新时间"
        self._attr_unique_id = f"{entry.entry_id}_update_time"
        self._attr_icon = "mdi:clock-check-outline"
        self._attr_device_class = "timestamp"  # 使用timestamp设备类
    
    @property
    def native_value(self):
        """返回传感器值."""
        if self.coordinator.data and "last_update" in self.coordinator.data:
            return self.coordinator.data["last_update"]
        return None
    
    @property
    def extra_state_attributes(self):
        """返回传感器属性."""
        attrs = {
            "query_year": self.coordinator.data.get("query_year", "") if self.coordinator.data else "",
            "update_interval": "24小时",  # 显示更新间隔
        }
        
        if self.coordinator.data and "error" in self.coordinator.data:
            attrs["error"] = self.coordinator.data["error"]
            
        return attrs
    
    @property
    def available(self):
        """返回传感器是否可用."""
        # 只有当有更新时间数据时才显示为可用
        return (self.coordinator.data is not None and 
                "last_update" in self.coordinator.data and 
                self.coordinator.data["last_update"] is not None)