from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.db.models import PaymentMethod, ProductPlan


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Buy Service"), KeyboardButton(text="My Services")],
            [KeyboardButton(text="Wallet"), KeyboardButton(text="Invite Friends")],
            [KeyboardButton(text="Charge Wallet"), KeyboardButton(text="Test Account")],
            [KeyboardButton(text="Support: @kasrazandi")],
        ],
        resize_keyboard=True,
    )


def service_types(plans: list[ProductPlan]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{plan.name} - {plan.price_per_gb_toman:,} Toman/GB",
                    callback_data=f"buy_plan:{plan.id}",
                )
            ]
            for plan in plans
        ]
    )


def payment_methods(enabled: set[str]) -> InlineKeyboardMarkup:
    rows = []
    labels = {
        PaymentMethod.card.value: "Card-to-card",
        PaymentMethod.plisio.value: "Plisio",
        PaymentMethod.nowpayments.value: "NOWPayments",
        PaymentMethod.stars.value: "Telegram Stars",
    }
    for method, label in labels.items():
        if method in enabled:
            rows.append([InlineKeyboardButton(text=label, callback_data=f"pay:{method}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def receipt_button(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Send Receipt", callback_data=f"receipt:{payment_id}")]]
    )


def service_actions(service_id: int, disabled: bool) -> InlineKeyboardMarkup:
    rows = []
    if disabled:
        rows.append([InlineKeyboardButton(text="Reactivate", callback_data=f"svc_reactivate:{service_id}")])
    rows.append([InlineKeyboardButton(text="Delete", callback_data=f"svc_delete:{service_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
