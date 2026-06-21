from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import PaymentMethod, ProductPlan


def service_types(plans: list[ProductPlan]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=plan.name,
                    callback_data=f"buy_plan:{plan.id}",
                )
            ]
            for plan in plans
        ]
    )


def plan_detail_actions(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="خرید این سرویس", callback_data=f"buy_plan_confirm:{plan_id}")],
            [InlineKeyboardButton(text="بازگشت به تعرفه‌ها", callback_data="buy_plans_back")],
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
    return InlineKeyboardMarkup(inline_keyboard=rows)


def receipt_button(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="ارسال رسید", callback_data=f"receipt:{payment_id}")]]
    )


def service_actions(service_id: int, disabled: bool) -> InlineKeyboardMarkup:
    rows = []
    if disabled:
        rows.append([InlineKeyboardButton(text="فعال‌سازی مجدد", callback_data=f"svc_reactivate:{service_id}")])
    rows.append([InlineKeyboardButton(text="حذف سرویس", callback_data=f"svc_delete:{service_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
