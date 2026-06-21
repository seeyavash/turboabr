from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.admin import (
    admin_menu,
    admin_id_actions,
    admin_service_actions,
    admin_user_actions,
    admins_menu,
    panel_actions,
    panels_list_keyboard,
    plan_panel_keyboard,
    panels_menu,
    payment_settings_menu,
    payment_toggle_keyboard,
    plan_actions,
    store_menu,
    supergroup_menu,
    menu_button_actions,
    menu_button_color_keyboard,
    menu_label,
    menu_buttons_keyboard,
    test_panel_keyboard,
    test_settings_menu,
    user_services_menu,
)
from app.db.models import PanelTemplate, PasarGuardPanel, PaymentRequest, PaymentStatus, ProductPlan, ServiceStatus, TransactionKind, User, VpnService
from app.services.catalog import CatalogService
from app.services.menu import ACTION_LABELS, COLOR_LABELS, MenuService
from app.services.notifications import send_supergroup_message
from app.services.payments import PaymentService
from app.services.services import VpnServiceManager
from app.services.settings import SettingsService
from app.services.wallet import WalletService

router = Router()


def menu_layout_text(buttons: list[dict]) -> str:
    rows = []
    for index in range(0, len(buttons), 2):
        row = []
        for offset, button in enumerate(buttons[index:index + 2]):
            row.append(f"{index + offset + 1}. {menu_label(button)}")
        rows.append(" | ".join(row))
    return "\n".join(rows)


def status_label(status: str) -> str:
    return {
        ServiceStatus.active.value: "فعال",
        ServiceStatus.disabled.value: "غیرفعال",
        ServiceStatus.deleted.value: "حذف‌شده",
    }.get(status, status)


class AdminState(StatesGroup):
    set_value = State()
    card_number = State()
    card_holder = State()
    supergroup_chat_id = State()
    menu_button_text = State()
    menu_button_icon = State()
    panel_name = State()
    panel_url = State()
    panel_username = State()
    panel_password = State()
    template_name = State()
    template_groups = State()
    template_client_type = State()
    plan_name = State()
    plan_description = State()
    plan_price = State()
    plan_panel = State()
    edit_plan = State()
    add_admin = State()
    user_lookup = State()
    broadcast = State()
    wallet_adjust = State()


async def is_admin(session: AsyncSession, telegram_id: int) -> bool:
    return telegram_id in await SettingsService(session).admin_ids()


async def replace_message(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


async def send_step_prompt(message: Message, state: FSMContext, text: str, reply_markup=None) -> None:
    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    if prompt_id:
        try:
            await message.bot.delete_message(message.chat.id, prompt_id)
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass
    sent = await message.answer(text, reply_markup=reply_markup)
    await state.update_data(prompt_message_id=sent.message_id)


async def cleanup_step_prompt(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    if prompt_id:
        try:
            await message.bot.delete_message(message.chat.id, prompt_id)
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass


async def show_panels(message: Message, session: AsyncSession) -> None:
    result = await session.execute(select(PasarGuardPanel).order_by(PasarGuardPanel.id))
    panels = list(result.scalars())
    if not panels:
        await message.answer("هنوز هیچ پنل PasarGuard ثبت نشده است.", reply_markup=panels_menu())
        return
    await message.answer("لیست پنل‌ها:", reply_markup=panels_list_keyboard(panels))


async def replace_with_panels(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(select(PasarGuardPanel).order_by(PasarGuardPanel.id))
    panels = list(result.scalars())
    if not panels:
        await replace_message(callback, "هنوز هیچ پنل PasarGuard ثبت نشده است.", reply_markup=panels_menu())
        return
    await replace_message(callback, "لیست پنل‌ها:", reply_markup=panels_list_keyboard(panels))


async def show_panel_detail(message: Message, session: AsyncSession, panel_id: int) -> None:
    panel = await session.get(PasarGuardPanel, panel_id)
    if not panel:
        await message.answer("پنل پیدا نشد.", reply_markup=panels_menu())
        return
    templates = await CatalogService(session).templates_for_panel(panel.id)
    template_count = len(templates)
    await message.answer(
        f"پنل #{panel.id}\n"
        f"نام: {panel.name}\n"
        f"آدرس: {panel.base_url}\n"
        f"نام کاربری: {panel.username}\n"
        f"گروه پیش‌فرض: {','.join(str(item) for item in (panel.group_ids or [])) or '-'}\n"
        f"نوع کلاینت پیش‌فرض: {panel.subscription_client_type}\n"
        f"تعداد تمپلیت‌ها: {template_count}\n"
        f"فعال: {'بله' if panel.is_active else 'خیر'}",
        reply_markup=panel_actions(panel.id, panel.is_active),
    )


async def replace_with_panel_detail(callback: CallbackQuery, session: AsyncSession, panel_id: int) -> None:
    panel = await session.get(PasarGuardPanel, panel_id)
    if not panel:
        await replace_message(callback, "پنل پیدا نشد.", reply_markup=panels_menu())
        return
    templates = await CatalogService(session).templates_for_panel(panel.id)
    await replace_message(
        callback,
        f"پنل #{panel.id}\n"
        f"نام: {panel.name}\n"
        f"آدرس: {panel.base_url}\n"
        f"نام کاربری: {panel.username}\n"
        f"گروه پیش‌فرض: {','.join(str(item) for item in (panel.group_ids or [])) or '-'}\n"
        f"نوع کلاینت پیش‌فرض: {panel.subscription_client_type}\n"
        f"تعداد تمپلیت‌ها: {len(templates)}\n"
        f"فعال: {'بله' if panel.is_active else 'خیر'}",
        reply_markup=panel_actions(panel.id, panel.is_active),
    )


@router.message(Command("admin"))
async def admin(message: Message, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("شما به پنل مدیریت دسترسی ندارید.")
        return
    await message.answer("پنل مدیریت", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:menu")
async def admin_menu_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await replace_message(callback, "پنل مدیریت", reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:dashboard")
async def dashboard(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    users = await session.scalar(select(func.count(User.id)))
    active = await session.scalar(select(func.count(VpnService.id)).where(VpnService.status == ServiceStatus.active.value))
    disabled = await session.scalar(select(func.count(VpnService.id)).where(VpnService.status == ServiceStatus.disabled.value))
    wallet_sum = await session.scalar(select(func.coalesce(func.sum(User.wallet_balance_toman), 0)))
    await replace_message(
        callback,
        f"تعداد کاربران: {users}\nسرویس‌های فعال: {active}\nسرویس‌های غیرفعال: {disabled}\nمجموع موجودی کیف پول‌ها: {wallet_sum:,} تومان"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:buttons")
async def buttons_editor(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    buttons = await MenuService(session).buttons()
    await replace_message(
        callback,
        "ویرایش دکمه‌های منوی کاربر\n"
        "چیدمان اینجا مثل منوی کاربر دو ستونه است. یک دکمه را بزنید و با بالا/پایین/چپ/راست جابه‌جا کنید.",
        reply_markup=menu_buttons_keyboard(buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_button:"))
async def button_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    action = callback.data.split(":", 1)[1]
    buttons = await MenuService(session).buttons()
    button = next((item for item in buttons if item["action"] == action), None)
    if not button:
        await callback.answer("دکمه پیدا نشد.", show_alert=True)
        return
    index = buttons.index(button)
    await replace_message(
        callback,
        f"دکمه: {ACTION_LABELS.get(action, action)}\n"
        f"متن فعلی: {button.get('label', '-')}\n"
        f"رنگ: {COLOR_LABELS.get(button.get('color'), 'بدون رنگ')}\n"
        f"ایموجی پریمیوم: {button.get('icon_custom_emoji_id') or '-'}\n"
        f"وضعیت: {'نمایش داده می‌شود' if button.get('visible', True) else 'مخفی است'}\n"
        f"جایگاه: ردیف {index // 2 + 1}، ستون {index % 2 + 1}\n\n"
        "چیدمان فعلی:\n"
        f"{menu_layout_text(buttons)}\n\n"
        "برای جابه‌جایی از بالا/پایین/چپ/راست استفاده کنید.",
        reply_markup=menu_button_actions(button),
    )
    await callback.answer()


async def replace_with_button_detail(callback: CallbackQuery, session: AsyncSession, action: str) -> None:
    buttons = await MenuService(session).buttons()
    button = next((item for item in buttons if item["action"] == action), None)
    if not button:
        await replace_message(callback, "دکمه پیدا نشد.", reply_markup=menu_buttons_keyboard(buttons))
        return
    index = buttons.index(button)
    await replace_message(
        callback,
        f"دکمه: {ACTION_LABELS.get(action, action)}\n"
        f"متن فعلی: {button.get('label', '-')}\n"
        f"رنگ: {COLOR_LABELS.get(button.get('color'), 'بدون رنگ')}\n"
        f"ایموجی پریمیوم: {button.get('icon_custom_emoji_id') or '-'}\n"
        f"وضعیت: {'نمایش داده می‌شود' if button.get('visible', True) else 'مخفی است'}\n"
        f"جایگاه: ردیف {index // 2 + 1}، ستون {index % 2 + 1}\n\n"
        "چیدمان فعلی:\n"
        f"{menu_layout_text(buttons)}\n\n"
        "برای جابه‌جایی از بالا/پایین/چپ/راست استفاده کنید.",
        reply_markup=menu_button_actions(button),
    )


@router.callback_query(F.data.startswith("admin_button_move:"))
async def button_move(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    _, action, direction = callback.data.split(":", 2)
    moved = await MenuService(session).move_grid(action, direction)
    await replace_with_button_detail(callback, session, action)
    await callback.answer("جابجا شد." if moved else "از این جهت جایی برای حرکت ندارد.")


@router.callback_query(F.data.startswith("admin_button_text:"))
async def button_text_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    action = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(menu_button_action=action, prompt_message_id=callback.message.message_id)
    await state.set_state(AdminState.menu_button_text)
    await replace_message(callback, "متن جدید دکمه را ارسال کنید.\nایموجی معمولی را می‌توانید داخل متن بگذارید.")
    await callback.answer()


@router.message(AdminState.menu_button_text)
async def button_text_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    text = (message.text or "").strip()
    if not text:
        await send_step_prompt(message, state, "متن دکمه نمی‌تواند خالی باشد. دوباره ارسال کنید:")
        return
    data = await state.get_data()
    await MenuService(session).set_label(data["menu_button_action"], text)
    await cleanup_step_prompt(message, state)
    await state.clear()
    await message.answer(
        "متن دکمه ذخیره شد. کیبورد جدید:",
        reply_markup=await MenuService(session).reply_markup(),
    )


@router.callback_query(F.data.startswith("admin_button_color:"))
async def button_color_start(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    action = callback.data.split(":", 1)[1]
    await replace_message(
        callback,
        "رنگ دکمه را انتخاب کنید.\n"
        "این رنگ با فیلد رسمی KeyboardButton.style تلگرام ارسال می‌شود.",
        reply_markup=menu_button_color_keyboard(action),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_button_icon:"))
async def button_icon_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    action = callback.data.split(":", 1)[1]
    await state.clear()
    await state.update_data(menu_button_action=action, prompt_message_id=callback.message.message_id)
    await state.set_state(AdminState.menu_button_icon)
    await replace_message(
        callback,
        "خود ایموجی پریمیوم یا شناسه custom emoji را ارسال کنید.\n"
        "برای حذف ایموجی، `-` بفرستید.\n"
        "این مقدار در فیلد رسمی `icon_custom_emoji_id` ذخیره می‌شود.",
    )
    await callback.answer()


@router.message(AdminState.menu_button_icon)
async def button_icon_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    icon = (message.text or "").strip()
    for entity in message.entities or []:
        if entity.type == "custom_emoji" and entity.custom_emoji_id:
            icon = entity.custom_emoji_id
            break
    icon = "" if icon == "-" else icon
    data = await state.get_data()
    await MenuService(session).set_icon(data["menu_button_action"], icon)
    await cleanup_step_prompt(message, state)
    await state.clear()
    await message.answer(
        "ایموجی پریمیوم دکمه ذخیره شد. کیبورد جدید:",
        reply_markup=await MenuService(session).reply_markup(),
    )


@router.callback_query(F.data.startswith("admin_button_set_color:"))
async def button_color_save(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    _, action, color = callback.data.split(":", 2)
    await MenuService(session).set_color(action, color)
    await replace_with_button_detail(callback, session, action)
    await callback.answer("رنگ ذخیره شد.")


@router.callback_query(F.data.startswith("admin_button_toggle:"))
async def button_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    action = callback.data.split(":", 1)[1]
    await MenuService(session).toggle_visible(action)
    await replace_with_button_detail(callback, session, action)
    await callback.answer("ذخیره شد.")


@router.callback_query(F.data == "admin_buttons_reset")
async def buttons_reset(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await MenuService(session).reset()
    await replace_message(callback, "منو به حالت پیش‌فرض برگشت.", reply_markup=menu_buttons_keyboard(await MenuService(session).buttons()))
    await callback.answer("بازنشانی شد.")


@router.callback_query(F.data == "admin:panels")
async def panels_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await replace_message(callback, "مدیریت پنل‌ها", reply_markup=panels_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:store")
async def store_section(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await replace_message(callback, "تنظیمات فروشگاه", reply_markup=store_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:admins")
async def admins_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await replace_message(callback, "تنظیمات ادمین‌ها", reply_markup=admins_menu())
    await callback.answer()


def payment_value_label(key: str, value: str | None) -> str:
    if key.startswith("payment_") and key.endswith("_enabled"):
        return "فعال" if str(value).lower() == "true" else "غیرفعال"
    if key in {"plisio_api_token", "nowpayments_api_token"}:
        return "ثبت شده" if value else "ثبت نشده"
    return value or "-"


@router.callback_query(F.data == "admin:payment_settings")
async def payment_settings_section(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    values = await SettingsService(session).all_public()
    wanted = [
        "card_number",
        "card_holder",
        "payment_card_enabled",
        "payment_plisio_enabled",
        "payment_nowpayments_enabled",
        "payment_stars_enabled",
        "plisio_api_token",
        "nowpayments_api_token",
        "stars_to_toman_rate",
    ]
    labels = {
        "card_number": "شماره کارت",
        "card_holder": "نام صاحب کارت",
        "payment_card_enabled": "وضعیت کارت به کارت",
        "payment_plisio_enabled": "وضعیت Plisio",
        "payment_nowpayments_enabled": "وضعیت NOWPayments",
        "payment_stars_enabled": "وضعیت استارز",
        "plisio_api_token": "توکن Plisio",
        "nowpayments_api_token": "توکن NOWPayments",
        "stars_to_toman_rate": "نرخ هر استار",
    }
    lines = [f"{labels[key]}: {payment_value_label(key, values.get(key))}" for key in wanted]
    await replace_message(callback, "\n".join(lines), reply_markup=payment_settings_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:user_services")
async def user_services_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await replace_message(callback, "خدمات کاربر", reply_markup=user_services_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:test_settings")
async def test_settings_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    settings = SettingsService(session)
    enabled = await settings.get_bool("test_account_enabled", True)
    test_panel_id = await settings.get("test_panel_id", "")
    panel_name = "-"
    if test_panel_id:
        panel = await session.get(PasarGuardPanel, int(test_panel_id))
        panel_name = panel.name if panel else "پنل پیدا نشد"
    await replace_message(
        callback,
        f"تنظیمات اکانت تست\n"
        f"وضعیت: {'فعال' if enabled else 'غیرفعال'}\n"
        f"پنل تست: {panel_name}\n"
        f"حجم: ۱۰۰ مگابایت\n"
        f"مدت: ۱ روز",
        reply_markup=test_settings_menu(enabled),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_test_enabled:"))
async def test_enabled_set(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    value = callback.data.split(":", 1)[1]
    await SettingsService(session).set("test_account_enabled", value)
    await test_settings_section(callback, session)


@router.callback_query(F.data == "admin_test_panel_select")
async def test_panel_select(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    panels = await CatalogService(session).active_panels()
    if not panels:
        await replace_message(callback, "هیچ پنل فعالی پیدا نشد.", reply_markup=test_settings_menu(True))
        await callback.answer()
        return
    await replace_message(callback, "پنل اکانت تست را انتخاب کنید:", reply_markup=test_panel_keyboard(panels))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_test_panel:"))
async def test_panel_set(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if not panel:
        await callback.answer("پنل پیدا نشد.", show_alert=True)
        return
    await SettingsService(session).set("test_panel_id", str(panel.id))
    await test_settings_section(callback, session)


@router.callback_query(F.data == "admin:supergroup")
async def supergroup_section(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    settings = SettingsService(session)
    chat_id = await settings.get("supergroup_chat_id", "")
    await replace_message(
        callback,
        "تنظیم سوپرگروه\n"
        f"گروه فعلی: {chat_id or '-'}\n\n"
        "گروه را forum/supergroup کن، ربات را ادمین کن، بعد chat id گروه را از @myidbot بگیر و اینجا ثبت کن.",
        reply_markup=supergroup_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_supergroup:set")
async def supergroup_set_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await state.update_data(prompt_message_id=callback.message.message_id)
    await state.set_state(AdminState.supergroup_chat_id)
    await replace_message(callback, "آیدی عددی سوپرگروه را ارسال کنید.\nمثال: -1001234567890")
    await callback.answer()


@router.message(AdminState.supergroup_chat_id)
async def supergroup_chat_id_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    raw_chat_id = (message.text or "").strip()
    try:
        chat_id = int(raw_chat_id)
    except ValueError:
        await send_step_prompt(message, state, "آیدی گروه باید عددی باشد. دوباره ارسال کنید:")
        return
    topics = {
        "supergroup_users_thread_id": "کاربران",
        "supergroup_receipts_thread_id": "رسیدها",
        "supergroup_errors_thread_id": "خطاها",
        "supergroup_orders_thread_id": "خرید و تمدید",
        "supergroup_account_changes_thread_id": "تغییرات اکانت",
    }
    settings = SettingsService(session)
    try:
        await settings.set("supergroup_chat_id", str(chat_id))
        for key, title in topics.items():
            topic = await message.bot.create_forum_topic(chat_id, title)
            await settings.set(key, str(topic.message_thread_id))
    except Exception as exc:
        await cleanup_step_prompt(message, state)
        await state.clear()
        await message.answer(f"خطا در ساخت تاپیک‌ها:\n{exc}\n\nمطمئن شو گروه forum است و ربات ادمین شده.")
        return
    await cleanup_step_prompt(message, state)
    await state.clear()
    await message.answer("سوپرگروه با موفقیت وصل شد و تاپیک‌ها ساخته شدند.")


@router.callback_query(F.data == "admin_panel:add")
async def add_panel_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await state.update_data(panel_mode="add", prompt_message_id=callback.message.message_id)
    await state.set_state(AdminState.panel_name)
    await replace_message(callback, "نام پنل را وارد کنید:")
    await callback.answer()


@router.callback_query(F.data == "admin_panel:list")
async def panels_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await replace_with_panels(callback, session)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_panel_view:"))
async def panel_view(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await replace_with_panel_detail(callback, session, int(callback.data.split(":", 1)[1]))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_panel_edit:"))
async def edit_panel_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if not panel:
        await callback.answer("پنل پیدا نشد.", show_alert=True)
        return
    await state.clear()
    await state.update_data(
        panel_mode="edit",
        panel_id=panel.id,
        prompt_message_id=callback.message.message_id,
    )
    await state.set_state(AdminState.panel_name)
    await replace_message(callback, f"نام پنل را وارد کنید:\nمقدار فعلی: {panel.name}\nبرای حفظ مقدار فعلی `-` بفرستید.")
    await callback.answer()


@router.message(AdminState.panel_name)
async def panel_name_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    value = (message.text or "").strip()
    data = await state.get_data()
    if data.get("panel_mode") == "edit" and value == "-":
        panel = await session.get(PasarGuardPanel, data["panel_id"])
        value = panel.name if panel else ""
    if not value:
        await send_step_prompt(message, state, "نام پنل نمی‌تواند خالی باشد. دوباره نام پنل را وارد کنید:")
        return
    await state.update_data(panel_name=value)
    await state.set_state(AdminState.panel_url)
    current = ""
    if data.get("panel_mode") == "edit":
        panel = await session.get(PasarGuardPanel, data["panel_id"])
        current = f"\nمقدار فعلی: {panel.base_url}\nبرای حفظ مقدار فعلی `-` بفرستید." if panel else ""
    await send_step_prompt(message, state, f"آدرس پنل را وارد کنید:{current}")


@router.message(AdminState.panel_url)
async def panel_url_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    value = (message.text or "").strip().rstrip("/")
    data = await state.get_data()
    if data.get("panel_mode") == "edit" and value == "-":
        panel = await session.get(PasarGuardPanel, data["panel_id"])
        value = panel.base_url if panel else ""
    if not value.startswith(("http://", "https://")):
        await send_step_prompt(message, state, "آدرس پنل باید با http:// یا https:// شروع شود. دوباره وارد کنید:")
        return
    await state.update_data(panel_url=value)
    await state.set_state(AdminState.panel_username)
    current = ""
    if data.get("panel_mode") == "edit":
        panel = await session.get(PasarGuardPanel, data["panel_id"])
        current = f"\nمقدار فعلی: {panel.username}\nبرای حفظ مقدار فعلی `-` بفرستید." if panel else ""
    await send_step_prompt(message, state, f"نام کاربری پنل را وارد کنید:{current}")


@router.message(AdminState.panel_username)
async def panel_username_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    value = (message.text or "").strip()
    data = await state.get_data()
    if data.get("panel_mode") == "edit" and value == "-":
        panel = await session.get(PasarGuardPanel, data["panel_id"])
        value = panel.username if panel else ""
    if not value:
        await send_step_prompt(message, state, "نام کاربری نمی‌تواند خالی باشد. دوباره وارد کنید:")
        return
    await state.update_data(panel_username=value)
    await state.set_state(AdminState.panel_password)
    suffix = "\nبرای حفظ رمز فعلی `-` بفرستید." if data.get("panel_mode") == "edit" else ""
    await send_step_prompt(message, state, f"رمز عبور پنل را وارد کنید:{suffix}")


@router.message(AdminState.panel_password)
async def panel_password_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    from app.core.security import encrypt_secret

    password = (message.text or "").strip()
    data = await state.get_data()
    try:
        if data.get("panel_mode") == "edit":
            panel = await session.get(PasarGuardPanel, data["panel_id"])
            if not panel:
                await cleanup_step_prompt(message, state)
                await state.clear()
                await message.answer("پنل پیدا نشد.", reply_markup=panels_menu())
                return
            panel.name = data["panel_name"]
            panel.base_url = data["panel_url"]
            panel.username = data["panel_username"]
            if password != "-":
                if not password:
                    await send_step_prompt(message, state, "رمز عبور نمی‌تواند خالی باشد. دوباره وارد کنید:")
                    return
                panel.password_secret = encrypt_secret(password) or ""
            success_text = "پنل با موفقیت ویرایش شد."
        else:
            if not password:
                await send_step_prompt(message, state, "رمز عبور نمی‌تواند خالی باشد. دوباره وارد کنید:")
                return
            panel = await CatalogService(session).add_panel(
                name=data["panel_name"],
                base_url=data["panel_url"],
                username=data["panel_username"],
                password=password,
                group_ids=[],
                subscription_client_type="v2ray",
            )
            success_text = "پنل با موفقیت اضافه شد."
        await cleanup_step_prompt(message, state)
        await state.clear()
        await message.answer(success_text)
        await show_panels(message, session)
    except Exception as exc:
        await cleanup_step_prompt(message, state)
        await state.clear()
        await message.answer(f"خطا در ذخیره پنل:\n{exc}", reply_markup=panels_menu())


@router.callback_query(F.data.startswith("admin_template_add:"))
async def add_template_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if not panel:
        await callback.answer("پنل پیدا نشد.", show_alert=True)
        return
    await state.clear()
    await state.update_data(template_panel_id=panel.id, prompt_message_id=callback.message.message_id)
    await state.set_state(AdminState.template_name)
    await replace_message(callback, f"نام تمپلیت را برای پنل «{panel.name}» وارد کنید:")
    await callback.answer()


@router.message(AdminState.template_name)
async def template_name_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    name = (message.text or "").strip()
    if not name:
        await send_step_prompt(message, state, "نام تمپلیت نمی‌تواند خالی باشد. دوباره وارد کنید:")
        return
    await state.update_data(template_name=name)
    await state.set_state(AdminState.template_groups)
    await send_step_prompt(message, state, "شناسه گروه‌های این تمپلیت را وارد کنید.\nاگر گروه ندارد، `-` بفرستید.\nنمونه: 1,2")


@router.message(AdminState.template_groups)
async def template_groups_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    raw = (message.text or "").strip()
    try:
        group_ids = [] if raw == "-" else [int(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError:
        await send_step_prompt(message, state, "شناسه گروه‌ها باید عددی باشد. نمونه: 1,2\nاگر گروه ندارد، `-` بفرستید.")
        return
    await state.update_data(template_group_ids=group_ids)
    await state.set_state(AdminState.template_client_type)
    await send_step_prompt(message, state, "نوع کلاینت تمپلیت را وارد کنید.\nاگر مطمئن نیستید `v2ray` بفرستید:")


@router.message(AdminState.template_client_type)
async def template_client_type_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    client_type = (message.text or "").strip() or "v2ray"
    data = await state.get_data()
    try:
        template = await CatalogService(session).add_template(
            panel_id=data["template_panel_id"],
            name=data["template_name"],
            group_ids=data["template_group_ids"],
            subscription_client_type=client_type,
        )
        await cleanup_step_prompt(message, state)
        await state.clear()
        await message.answer(f"تمپلیت با موفقیت اضافه شد: #{template.id} {template.name}")
        await show_panel_detail(message, session, template.panel_id)
    except Exception as exc:
        await cleanup_step_prompt(message, state)
        await state.clear()
        await message.answer(f"خطا در ذخیره تمپلیت:\n{exc}", reply_markup=panels_menu())


@router.callback_query(F.data.startswith("admin_template_list:"))
async def template_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    panel_id = int(callback.data.split(":", 1)[1])
    panel = await session.get(PasarGuardPanel, panel_id)
    if not panel:
        await replace_message(callback, "پنل پیدا نشد.", reply_markup=panels_menu())
        await callback.answer()
        return
    templates = await CatalogService(session).templates_for_panel(panel_id)
    if not templates:
        await replace_message(callback, "برای این پنل هنوز تمپلیتی ثبت نشده است.", reply_markup=panel_actions(panel_id, panel.is_active))
        await callback.answer()
        return
    lines = ["تمپلیت‌های این پنل:"]
    for template in templates:
        lines.append(
            f"\nتمپلیت #{template.id}\n"
            f"نام: {template.name}\n"
            f"گروه‌ها: {','.join(str(item) for item in template.group_ids) or '-'}\n"
            f"نوع کلاینت: {template.subscription_client_type}"
        )
    await replace_message(callback, "\n".join(lines), reply_markup=panel_actions(panel_id, panel.is_active))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_panel_enable:"))
async def enable_panel(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if panel:
        panel.is_active = True
        await replace_with_panel_detail(callback, session, panel.id)
    await callback.answer("پنل فعال شد.")


@router.callback_query(F.data.startswith("admin_panel_disable:"))
async def disable_panel(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if panel:
        panel.is_active = False
        await replace_with_panel_detail(callback, session, panel.id)
    await callback.answer("پنل غیرفعال شد.")


@router.callback_query(F.data.startswith("admin_panel_delete:"))
async def delete_panel(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if panel:
        plan_count = await session.scalar(select(func.count(ProductPlan.id)).where(ProductPlan.panel_id == panel.id))
        service_count = await session.scalar(select(func.count(VpnService.id)).where(VpnService.panel_id == panel.id))
        if plan_count or service_count:
            panel.is_active = False
            await replace_with_panel_detail(callback, session, panel.id)
            await callback.answer("این پنل تعرفه یا سرویس دارد؛ به جای حذف، غیرفعال شد.", show_alert=True)
            return
        await session.delete(panel)
    await replace_with_panels(callback, session)
    await callback.answer("پنل حذف شد.")


@router.callback_query(F.data == "admin_plan:add")
async def add_plan_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    panels = await CatalogService(session).active_panels()
    if not panels:
        await replace_message(callback, "اول از بخش مدیریت پنل‌ها یک پنل فعال اضافه کنید.", reply_markup=store_menu())
        await callback.answer()
        return
    await state.clear()
    await state.update_data(prompt_message_id=callback.message.message_id)
    await state.set_state(AdminState.plan_name)
    await replace_message(callback, "نام تعرفه را وارد کنید.\nمثال: مولتی هوشمند")
    await callback.answer()


@router.message(AdminState.plan_name)
async def plan_name_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    name = (message.text or "").strip()
    if not name:
        await send_step_prompt(message, state, "نام تعرفه نمی‌تواند خالی باشد. دوباره نام را وارد کنید:")
        return
    await state.update_data(plan_name=name)
    await state.set_state(AdminState.plan_description)
    await send_step_prompt(
        message,
        state,
        "توضیحات تعرفه را وارد کنید.\n"
        "این متن بعد از زدن دکمه خرید سرویس به کاربر نمایش داده می‌شود.\n"
        "مثال: هر گیگ ۹ هزار تومان، مناسب استفاده روزمره",
    )


@router.message(AdminState.plan_description)
async def plan_description_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    description = (message.text or "").strip()
    if not description:
        await send_step_prompt(message, state, "توضیحات نمی‌تواند خالی باشد. دوباره توضیحات را وارد کنید:")
        return
    await state.update_data(plan_description=description)
    await state.set_state(AdminState.plan_price)
    await send_step_prompt(message, state, "قیمت هر گیگ را به تومان و فقط عددی وارد کنید.\nمثال: 9000")


@router.message(AdminState.plan_price)
async def plan_price_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    raw_price = (message.text or "").replace(",", "").strip()
    try:
        price = int(raw_price)
    except ValueError:
        await send_step_prompt(message, state, "قیمت باید فقط عدد باشد. مثال: 9000")
        return
    if price <= 0:
        await send_step_prompt(message, state, "قیمت باید بیشتر از صفر باشد. دوباره وارد کنید:")
        return
    panels = await CatalogService(session).active_panels()
    if not panels:
        await cleanup_step_prompt(message, state)
        await state.clear()
        await message.answer("هیچ پنل فعالی پیدا نشد. اول یک پنل فعال اضافه کنید.", reply_markup=store_menu())
        return
    await state.update_data(plan_price=price)
    await state.set_state(AdminState.plan_panel)
    await send_step_prompt(message, state, "این تعرفه روی کدام پنل ساخته شود؟", reply_markup=plan_panel_keyboard(panels))


@router.callback_query(F.data.startswith("admin_plan_panel:"))
async def plan_panel_step(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    panel = await session.get(PasarGuardPanel, int(callback.data.split(":", 1)[1]))
    if not panel or not panel.is_active:
        await callback.answer("پنل پیدا نشد یا غیرفعال است.", show_alert=True)
        return
    data = await state.get_data()
    required = {"plan_name", "plan_description", "plan_price"}
    if not required.issubset(data):
        await state.clear()
        await replace_message(callback, "اطلاعات تعرفه کامل نیست. لطفاً دوباره افزودن تعرفه را شروع کنید.", reply_markup=store_menu())
        await callback.answer()
        return
    try:
        plan = await CatalogService(session).add_plan(
            name=data["plan_name"],
            description=data["plan_description"],
            price_per_gb_toman=data["plan_price"],
            panel_id=panel.id,
        )
    except Exception as exc:
        await session.rollback()
        await state.clear()
        await replace_message(callback, f"خطا در ذخیره تعرفه:\n{exc}", reply_markup=store_menu())
        await callback.answer()
        return
    await state.clear()
    await replace_message(
        callback,
        f"تعرفه با موفقیت اضافه شد.\n\n"
        f"#{plan.id} {plan.name}\n"
        f"پنل: {panel.name}\n"
        f"قیمت هر گیگ: {plan.price_per_gb_toman:,} تومان",
        reply_markup=store_menu(),
    )
    await callback.answer("تعرفه اضافه شد.")


@router.callback_query(F.data == "admin_plan:list")
async def plans_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    result = await session.execute(select(ProductPlan).order_by(ProductPlan.id))
    plans = list(result.scalars())
    if not plans:
        await callback.message.answer("هنوز هیچ تعرفه‌ای ثبت نشده است.")
    else:
        for plan in plans:
            await callback.message.answer(
                f"تعرفه #{plan.id}\n"
                f"نام: {plan.name}\n"
                f"توضیحات: {plan.description or '-'}\n"
                f"قیمت: {plan.price_per_gb_toman:,} تومان / گیگ\n"
                f"پنل: {plan.panel_id or 'پیش‌فرض'}\n"
                f"فعال: {'بله' if plan.is_active else 'خیر'}",
                reply_markup=plan_actions(plan.id, plan.is_active),
            )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_plan_edit:"))
async def edit_plan_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    plan = await session.get(ProductPlan, int(callback.data.split(":", 1)[1]))
    if not plan:
        await callback.answer("تعرفه پیدا نشد.", show_alert=True)
        return
    await state.update_data(plan_id=plan.id)
    await state.set_state(AdminState.edit_plan)
    await callback.message.answer(
        "اطلاعات فعلی تعرفه:\n"
        f"نام: {plan.name}\n"
        f"توضیحات: {plan.description or '-'}\n"
        f"قیمت هر گیگ: {plan.price_per_gb_toman}\n"
        f"شناسه پنل: {plan.panel_id or ''}\n\n"
        "اطلاعات جدید را ارسال کنید:\n"
        "نام تعرفه | توضیحات | قیمت هر گیگ به تومان | شناسه پنل (اختیاری)"
    )
    await callback.answer()


@router.message(AdminState.edit_plan)
async def edit_plan_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    plan = await session.get(ProductPlan, (await state.get_data())["plan_id"])
    if not plan:
        await message.answer("تعرفه پیدا نشد.")
        await state.clear()
        return
    parts = [part.strip() for part in (message.text or "").split("|")]
    if len(parts) not in {3, 4}:
        await message.answer("فرمت درست: نام تعرفه | توضیحات | قیمت هر گیگ به تومان | شناسه پنل (اختیاری)")
        return
    try:
        price = int(parts[2].replace(",", ""))
        panel_id = int(parts[3]) if len(parts) == 4 and parts[3] else None
    except ValueError:
        await message.answer("قیمت و شناسه پنل باید عددی باشند.")
        return
    if panel_id and not await session.get(PasarGuardPanel, panel_id):
        await message.answer("پنل پیدا نشد.")
        return
    plan.name = parts[0]
    plan.description = parts[1]
    plan.price_per_gb_toman = price
    plan.panel_id = panel_id
    await state.clear()
    await message.answer(f"تعرفه بروزرسانی شد: #{plan.id} {plan.name}")


@router.callback_query(F.data.startswith("admin_plan_enable:"))
async def enable_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    plan = await session.get(ProductPlan, int(callback.data.split(":", 1)[1]))
    if plan:
        plan.is_active = True
    await callback.answer("تعرفه فعال شد.")


@router.callback_query(F.data.startswith("admin_plan_disable:"))
async def disable_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    plan = await session.get(ProductPlan, int(callback.data.split(":", 1)[1]))
    if plan:
        plan.is_active = False
    await callback.answer("تعرفه غیرفعال شد.")


@router.callback_query(F.data.startswith("admin_plan_delete:"))
async def delete_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    plan = await session.get(ProductPlan, int(callback.data.split(":", 1)[1]))
    if plan:
        service_count = await session.scalar(select(func.count(VpnService.id)).where(VpnService.plan_id == plan.id))
        if service_count:
            plan.is_active = False
            await callback.answer("این تعرفه سرویس دارد؛ به جای حذف، غیرفعال شد.", show_alert=True)
            return
        await session.delete(plan)
    await callback.answer("تعرفه حذف شد.")


@router.callback_query(F.data == "admin_admin:add")
async def add_admin_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(AdminState.add_admin)
    await callback.message.answer("آیدی عددی تلگرام ادمین جدید را ارسال کنید:")
    await callback.answer()


@router.message(AdminState.add_admin)
async def add_admin_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    new_admin_id = int((message.text or "").strip())
    settings = SettingsService(session)
    ids = await settings.admin_ids()
    ids.add(new_admin_id)
    await settings.set("admin_ids", ",".join(str(item) for item in sorted(ids)))
    await state.clear()
    await message.answer(f"ادمین اضافه شد: {new_admin_id}")


@router.callback_query(F.data == "admin_admin:list")
async def admins_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    ids = await SettingsService(session).admin_ids()
    if not ids:
        await callback.message.answer("هیچ ادمینی ثبت نشده است.")
    for admin_id in sorted(ids):
        await callback.message.answer(f"آیدی ادمین: {admin_id}", reply_markup=admin_id_actions(admin_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_admin_remove:"))
async def remove_admin(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    admin_id = int(callback.data.split(":", 1)[1])
    if admin_id == callback.from_user.id:
        await callback.answer("نمی‌توانید خودتان را از این بخش حذف کنید.", show_alert=True)
        return
    settings = SettingsService(session)
    configured = await settings.get("admin_ids", "")
    ids = {int(item.strip()) for item in (configured or "").split(",") if item.strip()}
    if admin_id not in ids:
        await callback.answer("این ادمین از ENV آمده یا از این بخش قابل حذف نیست.", show_alert=True)
        return
    ids.remove(admin_id)
    await settings.set("admin_ids", ",".join(str(item) for item in sorted(ids)))
    await callback.answer("ادمین حذف شد.")


@router.callback_query(F.data == "admin_user:lookup")
async def user_lookup_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(AdminState.user_lookup)
    await callback.message.answer("آیدی عددی تلگرام کاربر را ارسال کنید:")
    await callback.answer()


async def send_admin_user_info(message: Message, session: AsyncSession, telegram_id: int) -> None:
    user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    if not user:
        await message.answer("کاربر پیدا نشد.")
        return
    result = await session.execute(select(VpnService).where(VpnService.user_id == user.id))
    services = list(result.scalars())
    active_count = len([service for service in services if service.status == ServiceStatus.active.value])
    disabled_count = len([service for service in services if service.status == ServiceStatus.disabled.value])
    await message.answer(
        f"کاربر: {user.telegram_id}\n"
        f"نام: {user.full_name or '-'}\n"
        f"یوزرنیم: @{user.username or '-'}\n"
        f"موجودی: {user.wallet_balance_toman:,} تومان\n"
        f"سرویس‌ها: {len(services)} کل، {active_count} فعال، {disabled_count} غیرفعال\n"
        f"اکانت تست گرفته: {'بله' if user.has_test_account else 'خیر'}\n"
        f"مسدود: {'بله' if user.is_blocked else 'خیر'}",
        reply_markup=admin_user_actions(user.id, user.is_blocked),
    )


@router.message(AdminState.user_lookup)
async def user_lookup_state(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    await send_admin_user_info(message, session, int((message.text or "").strip()))
    await state.clear()


@router.callback_query(F.data == "admin:users")
async def users_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    result = await session.execute(select(User).order_by(User.created_at.desc()).limit(20))
    users = list(result.scalars())
    if not users:
        await callback.message.answer("هنوز کاربری ثبت نشده است.")
    else:
        lines = [
            f"{user.telegram_id} | {user.full_name or '-'} | {user.wallet_balance_toman:,} تومان"
            for user in users
        ]
        await callback.message.answer("آخرین کاربران:\n" + "\n".join(lines))
    await callback.answer()


@router.callback_query(F.data == "admin:services")
async def services_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    result = await session.execute(
        select(VpnService, User)
        .join(User, User.id == VpnService.user_id)
        .where(VpnService.status != ServiceStatus.deleted.value)
        .order_by(VpnService.created_at.desc())
        .limit(20)
    )
    rows = list(result.all())
    if not rows:
        await callback.message.answer("هنوز سرویسی ثبت نشده است.")
    for service, user in rows:
        await callback.message.answer(
            f"سرویس #{service.id}\n"
            f"کاربر: {user.telegram_id}\n"
            f"نوع: {service.type}\n"
            f"وضعیت: {status_label(service.status)}\n"
            f"ترافیک محاسبه‌شده: {service.total_billed_mb} مگابایت",
            reply_markup=admin_service_actions(service.id, service.status == ServiceStatus.disabled.value),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_set:"))
async def admin_set_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    labels = {
        "card_info": "اطلاعات کارت",
        "payment_card_enabled": "وضعیت کارت به کارت",
        "payment_plisio_enabled": "وضعیت Plisio",
        "payment_nowpayments_enabled": "وضعیت NOWPayments",
        "payment_stars_enabled": "وضعیت استارز",
        "plisio_api_token": "توکن Plisio",
        "nowpayments_api_token": "توکن NOWPayments",
        "stars_to_toman_rate": "نرخ هر استار",
        "low_balance_threshold": "حد هشدار کمبود موجودی",
        "referral_cashback_percent": "درصد کش‌بک معرفی",
    }
    current = await SettingsService(session).get(key, "")
    await state.clear()
    await state.update_data(setting_key=key)
    if key == "card_info":
        current_card = await SettingsService(session).get("card_number", "")
        await state.update_data(prompt_message_id=callback.message.message_id)
        await state.set_state(AdminState.card_number)
        await replace_message(callback, f"شماره کارت را وارد کنید.\nمقدار فعلی: {current_card or '-'}")
        await callback.answer()
        return
    if key.startswith("payment_") and key.endswith("_enabled"):
        await replace_message(
            callback,
            f"{labels.get(key, key)} را انتخاب کنید.\nوضعیت فعلی: {payment_value_label(key, current)}",
            reply_markup=payment_toggle_keyboard(key),
        )
        await callback.answer()
        return
    await state.set_state(AdminState.set_value)
    await replace_message(
        callback,
        f"{labels.get(key, key)} را وارد کنید.\n"
        f"مقدار فعلی: {payment_value_label(key, current)}",
    )
    await callback.answer()


@router.message(AdminState.card_number)
async def admin_card_number(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    card = (message.text or "").strip().replace(" ", "").replace("-", "")
    if not card.isdigit() or len(card) < 12:
        await send_step_prompt(message, state, "شماره کارت معتبر نیست. شماره کارت را فقط عددی وارد کنید:")
        return
    await state.update_data(card_number=card)
    holder = await SettingsService(session).get("card_holder", "")
    await state.set_state(AdminState.card_holder)
    await send_step_prompt(message, state, f"نام صاحب کارت را وارد کنید.\nمقدار فعلی: {holder or '-'}")


@router.message(AdminState.card_holder)
async def admin_card_holder(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    holder = (message.text or "").strip()
    if not holder:
        await send_step_prompt(message, state, "نام صاحب کارت نمی‌تواند خالی باشد. دوباره وارد کنید:")
        return
    data = await state.get_data()
    settings = SettingsService(session)
    await settings.set("card_number", data["card_number"])
    await settings.set("card_holder", holder)
    await cleanup_step_prompt(message, state)
    await state.clear()
    await message.answer("اطلاعات کارت ذخیره شد.")


@router.callback_query(F.data.startswith("admin_set_bool:"))
async def admin_set_bool(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    _, key, value = callback.data.split(":", 2)
    await SettingsService(session).set(key, value)
    await replace_message(callback, "وضعیت ذخیره شد.", reply_markup=payment_settings_menu())
    await callback.answer("ذخیره شد.")


@router.message(AdminState.set_value)
async def admin_set_value(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    data = await state.get_data()
    key = data["setting_key"]
    service = SettingsService(session)
    value = (message.text or "").strip()
    if key == "stars_to_toman_rate" and (not value.isdigit() or int(value) <= 0):
        await message.answer("نرخ هر استار باید عددی و بیشتر از صفر باشد.")
        return
    await service.set(key, value)
    await state.clear()
    await message.answer("ذخیره شد.")


@router.callback_query(F.data == "admin:receipts")
async def pending_receipts(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    result = await session.execute(
        select(PaymentRequest).where(
            PaymentRequest.method == "card",
            PaymentRequest.status == PaymentStatus.pending.value,
        )
    )
    payments = list(result.scalars())
    if not payments:
        await callback.message.answer("رسید در انتظاری وجود ندارد.")
    for payment in payments:
        await callback.message.answer(f"رسید #{payment.id}: {payment.amount_toman:,} تومان")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_receipt_ok:"))
async def approve_receipt(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    payment = await session.get(PaymentRequest, int(callback.data.split(":", 1)[1]))
    if payment:
        await PaymentService(session).approve(payment, f"تایید شده توسط {callback.from_user.id}")
        user = await session.get(User, payment.user_id)
        if user:
            await callback.bot.send_message(user.telegram_id, f"رسید شما تایید شد. کیف پول به مبلغ {payment.amount_toman:,} تومان شارژ شد.")
        await send_supergroup_message(
            session,
            callback.bot,
            "receipts",
            f"رسید تایید شد\nرسید: #{payment.id}\nمبلغ: {payment.amount_toman:,} تومان\nادمین: {callback.from_user.id}",
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await callback.answer("تایید شد.")


@router.callback_query(F.data.startswith("admin_receipt_no:"))
async def reject_receipt(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    payment = await session.get(PaymentRequest, int(callback.data.split(":", 1)[1]))
    if payment:
        await PaymentService(session).reject(payment, f"رد شده توسط {callback.from_user.id}")
        user = await session.get(User, payment.user_id)
        if user:
            await callback.bot.send_message(user.telegram_id, "رسید شما رد شد. اگر فکر می‌کنید اشتباهی رخ داده، با پشتیبانی تماس بگیرید.")
        await send_supergroup_message(
            session,
            callback.bot,
            "receipts",
            f"رسید رد شد\nرسید: #{payment.id}\nمبلغ: {payment.amount_toman:,} تومان\nادمین: {callback.from_user.id}",
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await callback.answer("رد شد.")


@router.callback_query(F.data.startswith("admin_svc_disable:"))
async def admin_disable_service(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    service = await session.get(VpnService, int(callback.data.split(":", 1)[1]))
    if service:
        panel = await CatalogService(session).client_for_panel(service.panel_id)
        await VpnServiceManager(session, panel).disable(service)
        await send_supergroup_message(
            session,
            callback.bot,
            "account_changes",
            f"ادمین سرویس را غیرفعال کرد\nادمین: {callback.from_user.id}\nاکانت: {service.pasarguard_username}",
        )
    await callback.answer("غیرفعال شد.")


@router.callback_query(F.data.startswith("admin_svc_reactivate:"))
async def admin_reactivate_service(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    service = await session.get(VpnService, int(callback.data.split(":", 1)[1]))
    if service:
        panel = await CatalogService(session).client_for_panel(service.panel_id)
        await VpnServiceManager(session, panel).reenable(service)
        await send_supergroup_message(
            session,
            callback.bot,
            "orders",
            f"ادمین سرویس را فعال کرد\nادمین: {callback.from_user.id}\nاکانت: {service.pasarguard_username}",
        )
    await callback.answer("فعال شد.")


@router.callback_query(F.data.startswith("admin_svc_delete:"))
async def admin_delete_service(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    service = await session.get(VpnService, int(callback.data.split(":", 1)[1]))
    if service:
        panel = await CatalogService(session).client_for_panel(service.panel_id)
        await VpnServiceManager(session, panel).delete(service)
        await send_supergroup_message(
            session,
            callback.bot,
            "account_changes",
            f"ادمین سرویس را حذف کرد\nادمین: {callback.from_user.id}\nاکانت: {service.pasarguard_username}",
        )
    await callback.answer("حذف شد.")


@router.callback_query(F.data.startswith("admin_user_block:"))
async def admin_block_user(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    user = await session.get(User, int(callback.data.split(":", 1)[1]))
    if user:
        user.is_blocked = True
        result = await session.execute(
            select(VpnService).where(
                VpnService.user_id == user.id,
                VpnService.status == ServiceStatus.active.value,
            )
        )
        for service in result.scalars():
            panel = await CatalogService(session).client_for_panel(service.panel_id)
            await VpnServiceManager(session, panel).disable(service)
    await callback.answer("کاربر مسدود شد.")


@router.callback_query(F.data.startswith("admin_user_unblock:"))
async def admin_unblock_user(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    user = await session.get(User, int(callback.data.split(":", 1)[1]))
    if user:
        user.is_blocked = False
    await callback.answer("مسدودی کاربر برداشته شد.")


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(AdminState.broadcast)
    await callback.message.answer("متن پیام همگانی را ارسال کنید:")
    await callback.answer()


@router.message(AdminState.broadcast)
async def broadcast_send(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    result = await session.execute(select(User.telegram_id))
    sent = 0
    for telegram_id in result.scalars():
        try:
            await message.bot.send_message(telegram_id, message.text or "")
            sent += 1
        except Exception:
            pass
    await state.clear()
    await message.answer(f"پیام همگانی برای {sent} کاربر ارسال شد.")


@router.message(Command("add_balance"))
async def add_balance(message: Message, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("فرمت دستور: /add_balance <telegram_id> <amount>")
        return
    user = (await session.execute(select(User).where(User.telegram_id == int(parts[1])))).scalar_one_or_none()
    if not user:
        await message.answer("کاربر پیدا نشد.")
        return
    await WalletService(session).add(user, int(parts[2]), TransactionKind.admin_adjustment, f"تغییر موجودی توسط ادمین {message.from_user.id}")
    await message.answer("موجودی بروزرسانی شد.")


@router.message(Command("remove_balance"))
async def remove_balance(message: Message, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("فرمت دستور: /remove_balance <telegram_id> <amount>")
        return
    user = (await session.execute(select(User).where(User.telegram_id == int(parts[1])))).scalar_one_or_none()
    if not user:
        await message.answer("کاربر پیدا نشد.")
        return
    amount = min(user.wallet_balance_toman, int(parts[2]))
    await WalletService(session).deduct(
        user,
        amount,
        f"کسر موجودی توسط ادمین {message.from_user.id}",
        {"admin_id": message.from_user.id},
    )
    await message.answer("موجودی بروزرسانی شد.")


@router.message(Command("user"))
async def user_lookup(message: Message, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("فرمت دستور: /user <telegram_id>")
        return
    await send_admin_user_info(message, session, int(parts[1]))


@router.message(Command("service_disable"))
async def service_disable(message: Message, session: AsyncSession) -> None:
    if not await is_admin(session, message.from_user.id):
        await message.answer("دسترسی ندارید.")
        return
    service = await session.get(VpnService, int((message.text or "").split()[1]))
    if service:
        panel = await CatalogService(session).client_for_panel(service.panel_id)
        await VpnServiceManager(session, panel).disable(service)
        await message.answer("سرویس غیرفعال شد.")
