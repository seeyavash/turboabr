from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.db.models import PaymentMethod, ProductPlan

CANCEL_TEXT = "منصرف شدم / بازگشت"


def cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True,
    )


def service_name_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="انتخاب نام خودکار")],
            [KeyboardButton(text=CANCEL_TEXT)],
        ],
        resize_keyboard=True,
    )


def service_types(plans: list[ProductPlan]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=plan.name,
                callback_data=f"buy_plan:{plan.id}",
            )
        ]
        for plan in plans
    ]
    rows.append([InlineKeyboardButton(text="لغو / بازگشت", callback_data="user_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_services_keyboard(services) -> InlineKeyboardMarkup:
    rows = []
    for service in services:
        username = service.pasarguard_username or f"سرویس #{service.id}"
        title = username if len(username) <= 36 else f"{username[:33]}..."
        rows.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"svc_view:{service.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="بازگشت", callback_data="user_services_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plan_detail_actions(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="خرید این سرویس", callback_data=f"buy_plan_confirm:{plan_id}")],
            [InlineKeyboardButton(text="بازگشت به تعرفه‌ها", callback_data="buy_plans_back")],
            [InlineKeyboardButton(text="لغو / بازگشت", callback_data="user_cancel")],
        ]
    )


def payment_methods(enabled: set[str]) -> InlineKeyboardMarkup:
    rows = []
    labels = {
        PaymentMethod.card.value: "کارت به کارت",
        PaymentMethod.plisio.value: "Plisio",
        PaymentMethod.nowpayments.value: "NOWPayments",
        PaymentMethod.stars.value: "استارز تلگرام",
    }
    for method, label in labels.items():
        if method in enabled:
            rows.append([InlineKeyboardButton(text=label, callback_data=f"pay:{method}")])
    rows.append([InlineKeyboardButton(text="لغو / بازگشت", callback_data="user_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def receipt_button(payment_id: int, card_number: str = "") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="ارسال رسید", callback_data=f"receipt:{payment_id}")]]
    if card_number:
        rows.append([InlineKeyboardButton(text="کپی شماره کارت", copy_text=CopyTextButton(text=card_number))])
    rows.append([InlineKeyboardButton(text="لغو", callback_data="user_cancel")])
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def service_actions(service_id: int, disabled: bool) -> InlineKeyboardMarkup:
    rows = []
    if disabled:
        rows.append([InlineKeyboardButton(text="فعال‌سازی مجدد", callback_data=f"svc_reactivate:{service_id}")])
    rows.append([InlineKeyboardButton(text="حذف سرویس", callback_data=f"svc_delete:{service_id}")])
    rows.append([InlineKeyboardButton(text="بازگشت به سرویس‌ها", callback_data="svc_list_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_link_keyboard(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="کپی لینک", copy_text=CopyTextButton(text=link))],
        ]
    )
