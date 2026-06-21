import json
from copy import deepcopy

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as env_settings
from app.services.settings import SettingsService

MENU_BUTTONS_KEY = "user_menu_buttons"

COLOR_PREFIXES = {
    "none": "",
    "green": "🟢",
    "blue": "🔵",
    "red": "🔴",
}

COLOR_LABELS = {
    "none": "بدون رنگ",
    "green": "سبز",
    "blue": "آبی",
    "red": "قرمز",
}

DEFAULT_MENU_BUTTONS = [
    {"action": "buy_service", "label": "خرید سرویس", "color": "none", "visible": True},
    {"action": "my_services", "label": "سرویس‌های من", "color": "none", "visible": True},
    {"action": "wallet", "label": "کیف پول", "color": "none", "visible": True},
    {"action": "invite", "label": "دعوت دوستان", "color": "none", "visible": True},
    {"action": "charge_wallet", "label": "شارژ کیف پول", "color": "none", "visible": True},
    {"action": "test_account", "label": "اکانت تست", "color": "none", "visible": True},
    {"action": "support", "label": "پشتیبانی: @{support_username}", "color": "none", "visible": True},
]

ACTION_LABELS = {
    "buy_service": "خرید سرویس",
    "my_services": "سرویس‌های من",
    "wallet": "کیف پول",
    "invite": "دعوت دوستان",
    "charge_wallet": "شارژ کیف پول",
    "test_account": "اکانت تست",
    "support": "پشتیبانی",
}


def normalize_buttons(buttons: list[dict]) -> list[dict]:
    by_action = {button.get("action"): button for button in buttons if button.get("action")}
    normalized = []
    for default in DEFAULT_MENU_BUTTONS:
        current = {**default, **by_action.get(default["action"], {})}
        current["color"] = current.get("color") if current.get("color") in COLOR_PREFIXES else "none"
        current["visible"] = bool(current.get("visible", True))
        normalized.append(current)
    return normalized


class MenuService:
    def __init__(self, session: AsyncSession):
        self.settings = SettingsService(session)

    async def buttons(self) -> list[dict]:
        raw = await self.settings.get(MENU_BUTTONS_KEY, "")
        if not raw:
            return deepcopy(DEFAULT_MENU_BUTTONS)
        try:
            return normalize_buttons(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            return deepcopy(DEFAULT_MENU_BUTTONS)

    async def save_buttons(self, buttons: list[dict]) -> None:
        await self.settings.set(MENU_BUTTONS_KEY, json.dumps(normalize_buttons(buttons), ensure_ascii=False))

    async def move(self, action: str, direction: int) -> None:
        buttons = await self.buttons()
        index = next((i for i, button in enumerate(buttons) if button["action"] == action), None)
        if index is None:
            return
        new_index = index + direction
        if new_index < 0 or new_index >= len(buttons):
            return
        buttons[index], buttons[new_index] = buttons[new_index], buttons[index]
        await self.save_buttons(buttons)

    async def set_label(self, action: str, label: str) -> None:
        buttons = await self.buttons()
        for button in buttons:
            if button["action"] == action:
                button["label"] = label
                break
        await self.save_buttons(buttons)

    async def set_color(self, action: str, color: str) -> None:
        buttons = await self.buttons()
        for button in buttons:
            if button["action"] == action and color in COLOR_PREFIXES:
                button["color"] = color
                break
        await self.save_buttons(buttons)

    async def toggle_visible(self, action: str) -> None:
        buttons = await self.buttons()
        for button in buttons:
            if button["action"] == action:
                button["visible"] = not button.get("visible", True)
                break
        await self.save_buttons(buttons)

    async def reset(self) -> None:
        await self.save_buttons(deepcopy(DEFAULT_MENU_BUTTONS))

    def display_text(self, button: dict) -> str:
        label = str(button.get("label") or "")
        label = label.replace("{support_username}", env_settings.support_username)
        prefix = COLOR_PREFIXES.get(str(button.get("color")), "")
        return f"{prefix} {label}" if prefix else label

    async def reply_markup(self) -> ReplyKeyboardMarkup:
        visible = [button for button in await self.buttons() if button.get("visible", True)]
        rows = []
        for index in range(0, len(visible), 2):
            rows.append([KeyboardButton(text=self.display_text(button)) for button in visible[index:index + 2]])
        return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

    async def action_for_text(self, text: str) -> str | None:
        text = (text or "").strip()
        for button in await self.buttons():
            if button.get("visible", True) and self.display_text(button) == text:
                return str(button["action"])
        return None
