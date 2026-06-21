import json
from copy import deepcopy

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as env_settings
from app.services.settings import SettingsService

MENU_BUTTONS_KEY = "user_menu_buttons"
MENU_COLUMNS = 2
LTR_MARK = "\u200e"

BUTTON_STYLES = {
    "none": None,
    "green": "success",
    "blue": "primary",
    "red": "danger",
}

COLOR_LABELS = {
    "none": "بدون رنگ",
    "green": "سبز",
    "blue": "آبی",
    "red": "قرمز",
}

DEFAULT_MENU_BUTTONS = [
    {"action": "buy_service", "label": "خرید سرویس", "color": "none", "icon_custom_emoji_id": "", "icon_text": "", "visible": True},
    {"action": "my_services", "label": "سرویس‌های من", "color": "none", "icon_custom_emoji_id": "", "icon_text": "", "visible": True},
    {"action": "wallet", "label": "کیف پول", "color": "none", "icon_custom_emoji_id": "", "icon_text": "", "visible": True},
    {"action": "invite", "label": "دعوت دوستان", "color": "none", "icon_custom_emoji_id": "", "icon_text": "", "visible": True},
    {"action": "charge_wallet", "label": "شارژ کیف پول", "color": "none", "icon_custom_emoji_id": "", "icon_text": "", "visible": True},
    {"action": "test_account", "label": "اکانت تست", "color": "none", "icon_custom_emoji_id": "", "icon_text": "", "visible": True},
    {"action": "support", "label": "پشتیبانی", "color": "none", "icon_custom_emoji_id": "", "icon_text": "", "visible": True},
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
    defaults = {button["action"]: button for button in DEFAULT_MENU_BUTTONS}
    seen = set()
    normalized = []

    for button in buttons:
        action = button.get("action")
        if action not in defaults or action in seen:
            continue
        seen.add(action)
        current = {**defaults[action], **button}
        current["color"] = current.get("color") if current.get("color") in BUTTON_STYLES else "none"
        current["icon_custom_emoji_id"] = str(current.get("icon_custom_emoji_id") or "")
        current["icon_text"] = str(current.get("icon_text") or "")
        current["visible"] = bool(current.get("visible", True))
        normalized.append(current)

    for default in DEFAULT_MENU_BUTTONS:
        if default["action"] in seen:
            continue
        normalized.append(default.copy())

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

    async def move_grid(self, action: str, direction: str) -> bool:
        buttons = await self.buttons()
        index = next((i for i, button in enumerate(buttons) if button["action"] == action), None)
        if index is None:
            return False
        column = index % MENU_COLUMNS
        if direction == "left":
            if column == 0:
                return False
            new_index = index - 1
        elif direction == "right":
            if column >= MENU_COLUMNS - 1:
                return False
            new_index = index + 1
        elif direction == "up":
            new_index = index - MENU_COLUMNS
        elif direction == "down":
            new_index = index + MENU_COLUMNS
        else:
            return False
        if new_index < 0 or new_index >= len(buttons):
            return False
        buttons[index], buttons[new_index] = buttons[new_index], buttons[index]
        await self.save_buttons(buttons)
        return True

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
            if button["action"] == action and color in BUTTON_STYLES:
                button["color"] = color
                break
        await self.save_buttons(buttons)

    async def set_icon(self, action: str, icon_custom_emoji_id: str, icon_text: str = "") -> None:
        buttons = await self.buttons()
        for button in buttons:
            if button["action"] == action:
                button["icon_custom_emoji_id"] = icon_custom_emoji_id
                button["icon_text"] = icon_text
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
        text = label.replace("{support_username}", env_settings.support_username)
        if button.get("icon_custom_emoji_id") and not text.startswith(LTR_MARK):
            return f"{LTR_MARK}{text}"
        return text

    def keyboard_button(self, button: dict) -> KeyboardButton:
        payload = {"text": self.display_text(button)}
        style = BUTTON_STYLES.get(str(button.get("color")))
        icon_custom_emoji_id = str(button.get("icon_custom_emoji_id") or "")
        if style:
            payload["style"] = style
        if icon_custom_emoji_id:
            payload["icon_custom_emoji_id"] = icon_custom_emoji_id
        return KeyboardButton(**payload)

    async def reply_markup(self) -> ReplyKeyboardMarkup:
        visible = [button for button in await self.buttons() if button.get("visible", True)]
        rows = []
        for index in range(0, len(visible), MENU_COLUMNS):
            rows.append([self.keyboard_button(button) for button in visible[index:index + MENU_COLUMNS]])
        return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

    async def action_for_text(self, text: str) -> str | None:
        text = (text or "").strip()
        for button in await self.buttons():
            if button.get("visible", True) and self.display_text(button) == text:
                return str(button["action"])
        return None
