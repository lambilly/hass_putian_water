"""配置流 for 莆田水费."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """处理配置流."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """处理用户步骤."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # 验证年份格式
                try:
                    year = int(user_input["query_year"])
                    if year < 2000 or year > 2100:
                        errors["query_year"] = "year_range_error"
                except ValueError:
                    errors["query_year"] = "invalid_year"
                
                # 验证水表号
                if not user_input["meter_number"].strip():
                    errors["meter_number"] = "meter_number_required"
                
                # 验证token
                if not user_input["token"].strip():
                    errors["token"] = "token_required"
                
                # 验证cookie
                if not user_input["cookie"].strip():
                    errors["cookie"] = "cookie_required"

                if not errors:
                    # 验证配置
                    from homeassistant.helpers.aiohttp_client import async_get_clientsession
                    session = async_get_clientsession(self.hass)
                    
                    # 创建临时 API 实例进行验证
                    from . import PutianWaterAPI
                    api = PutianWaterAPI(
                        session=session,
                        token=user_input["token"],
                        cookie=user_input["cookie"],
                        meter_number=user_input["meter_number"],
                        query_year=user_input["query_year"],
                        water_corp_id=int(user_input.get("water_corp_id", 3)),
                        area_id=int(user_input.get("area_id", 0))
                    )
                    
                    # 测试 API 连接
                    try:
                        success = await api.test_connection()
                        if not success:
                            errors["base"] = "api_error"
                    except Exception as err:
                        _LOGGER.error("API test failed: %s", err)
                        if "HTTP 500" in str(err) and "NumberFormatException" in str(err):
                            errors["base"] = "number_format_error"
                        elif "HTTP 500" in str(err):
                            errors["base"] = "server_error"
                        elif "Unexpected content type" in str(err):
                            errors["base"] = "invalid_response"
                        elif "Network error" in str(err):
                            errors["base"] = "network_error"
                        else:
                            errors["base"] = "auth_failed"
                    
                    if not errors:
                        # 创建唯一 ID
                        unique_id = f"putian_water_{user_input['meter_number']}"
                        await self.async_set_unique_id(unique_id)
                        self._abort_if_unique_id_configured()
                        
                        return self.async_create_entry(
                            title=f"莆田水费 - {user_input['meter_number']}",
                            data=user_input,
                        )
            except Exception as ex:
                _LOGGER.exception("配置验证失败")
                errors["base"] = "unknown_error"

        # 使用翻译系统
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("meter_number"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Required("token"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Required("cookie"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Required("query_year", default="2025"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Optional("water_corp_id", default=3): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=100, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional("area_id", default=0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=100, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
            }),
            errors=errors,
        )