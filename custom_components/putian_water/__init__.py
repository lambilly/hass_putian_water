"""莆田水费集成."""
from __future__ import annotations

import logging
import aiohttp
import json
import urllib.parse
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置配置条目."""
    hass.data.setdefault(DOMAIN, {})
    
    # 创建 API 实例
    session = async_get_clientsession(hass)
    hass.data[DOMAIN][entry.entry_id] = {
        "api": PutianWaterAPI(
            session=session,
            token=entry.data["token"],
            cookie=entry.data["cookie"],
            meter_number=entry.data["meter_number"],
            query_year=entry.data["query_year"],
            water_corp_id=entry.data.get("water_corp_id", 3),
            area_id=entry.data.get("area_id", 0)
        )
    }

    # 设置传感器平台
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置条目."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class PutianWaterAPI:
    """莆田水费 API 客户端."""
    
    def __init__(self, session, token, cookie, meter_number, query_year, water_corp_id=3, area_id=0):
        """初始化 API 客户端."""
        self._session = session
        self._token = token
        self._cookie = cookie
        self._meter_number = meter_number
        self._query_year = query_year
        # 确保water_corp_id和area_id是整数
        self._water_corp_id = int(water_corp_id) if water_corp_id else 3
        self._area_id = int(area_id) if area_id else 0
        self._base_url = "https://wt.ptswater.cn/iwater/v1/watermeter"
        
        self._headers = {
            "Connection": "keep-alive",
            "sec-ch-ua-platform": "\"Windows\"",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
            "Accept": "application/json, text/plain, */*",
            "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Microsoft Edge\";v=\"138\"",
            "Content-Type": "application/x-www-form-urlencoded",
            "sec-ch-ua-mobile": "?0",
            "Origin": "https://wt.ptswater.cn",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://wt.ptswater.cn/",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,zh-TW;q=0.5",
            "Cookie": cookie
        }
    
    async def _make_request(self, endpoint, data):
        """统一的请求方法."""
        try:
            # 准备请求数据 - 确保数字字段是整数而不是浮点数
            if isinstance(data, dict):
                # 转换数字字段为整数
                for key in ['waterCorpId', 'areaId']:
                    if key in data and data[key] is not None:
                        data[key] = int(data[key])
                
                payload = f'requestPara={urllib.parse.quote(json.dumps(data, ensure_ascii=False))}'
            else:
                payload = data
            
            # 复制headers并设置Content-Length
            headers = self._headers.copy()
            headers["Content-Length"] = str(len(payload))
            
            _LOGGER.debug("Making request to %s with data: %s", endpoint, data)
            
            async with self._session.post(
                f"{self._base_url}/{endpoint}",
                headers=headers,
                data=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                # 检查响应状态
                if response.status != 200:
                    text = await response.text()
                    _LOGGER.error("HTTP error %s: %s", response.status, text)
                    raise Exception(f"HTTP {response.status}: {text}")
                
                # 检查内容类型
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    text = await response.text()
                    _LOGGER.error("Unexpected content type: %s, response: %s", content_type, text)
                    raise Exception(f"Unexpected content type: {content_type}")
                
                # 解析JSON响应
                result = await response.json()
                _LOGGER.debug("Response received: %s", result)
                
                # 检查API响应状态 - 修复：服务器返回成功消息但success字段可能为false
                # 根据错误信息，服务器返回了"获取水表列表成功"但我们的代码错误处理了
                if "success" in result and not result["success"]:
                    error_msg = result.get("message", "Unknown error")
                    _LOGGER.error("API error: %s", error_msg)
                    raise Exception(f"API error: {error_msg}")
                
                # 如果没有success字段但包含数据，也认为是成功的
                if "data" not in result and "success" not in result:
                    _LOGGER.error("API response missing data and success fields: %s", result)
                    raise Exception("API response missing required fields")
                
                return result
                
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error: %s", err)
            raise Exception(f"Network error: {err}")
        except Exception as err:
            _LOGGER.error("Request failed: %s", err)
            raise
    
    async def get_user_meter_list(self):
        """获取用户水表列表."""
        request_body = {
            "UNID": "",
            "token": self._token,
            "waterCorpId": self._water_corp_id,  # 现在确保是整数
            "areaId": self._area_id,  # 现在确保是整数
            "accountType": "XJ",
            "apiType": "PC",
            "appVersion": "1.0.2"
        }
        
        return await self._make_request("queryUserMeterList/v1.json", request_body)
    
    async def get_payment_info(self):
        """获取缴费信息."""
        # 使用配置的年份生成日期范围
        year = self._query_year
        start_date = f"{year}0101"  # 如：20250101
        end_date = f"{year}1231"   # 如：20251231
        
        request_body = {
            "meterNumber": self._meter_number,
            "startDate": start_date,
            "endDate": end_date,
            "waterCorpId": self._water_corp_id,  # 现在确保是整数
            "payStatus": "2",
            "token": self._token,
            "UNID": "",
            "areaId": self._area_id,  # 现在确保是整数
            "accountType": "XJ",
            "apiType": "PC",
            "appVersion": "1.0.2"
        }
        
        return await self._make_request("queryPayMentInfo/v2.json", request_body)
    
    async def test_connection(self):
        """测试连接."""
        try:
            result = await self.get_user_meter_list()
            # 如果返回了数据，即使success字段为false，也认为是成功的
            # 根据错误信息，服务器返回了"获取水表列表成功"的消息
            if result.get("data") is not None or "获取水表列表成功" in str(result.get("message", "")):
                return True
            return result.get("success", False)
        except Exception as err:
            _LOGGER.error("Connection test failed: %s", err)
            return False