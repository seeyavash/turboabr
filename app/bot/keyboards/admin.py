from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Dashboard", callback_data="admin:dashboard")],
            [InlineKeyboardButton(text="Modiriate panelha", callback_data="admin:panels")],
            [InlineKeyboardButton(text="Tanzimat foroshgah", callback_data="admin:store")],
            [InlineKeyboardButton(text="Tanzimat adminha", callback_data="admin:admins")],
            [InlineKeyboardButton(text="Tanzimate pardakht", callback_data="admin:payment_settings")],
            [InlineKeyboardButton(text="Khadamate karbar", callback_data="admin:user_services")],
        ]
    )


def receipt_review(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Approve", callback_data=f"admin_receipt_ok:{payment_id}"),
                InlineKeyboardButton(text="Reject", callback_data=f"admin_receipt_no:{payment_id}"),
            ]
        ]
    )


def admin_back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Back to admin", callback_data="admin:menu")]]
    )


def panels_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Add PasarGuard panel", callback_data="admin_panel:add")],
            [InlineKeyboardButton(text="List panels", callback_data="admin_panel:list")],
            [InlineKeyboardButton(text="Back", callback_data="admin:menu")],
        ]
    )


def panel_actions(panel_id: int, active: bool) -> InlineKeyboardMarkup:
    toggle_text = "Disable" if active else "Enable"
    toggle_action = "disable" if active else "enable"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Edit", callback_data=f"admin_panel_edit:{panel_id}")],
            [InlineKeyboardButton(text=toggle_text, callback_data=f"admin_panel_{toggle_action}:{panel_id}")],
            [InlineKeyboardButton(text="Delete", callback_data=f"admin_panel_delete:{panel_id}")],
            [InlineKeyboardButton(text="Back", callback_data="admin:panels")],
        ]
    )


def store_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Add tariff", callback_data="admin_plan:add")],
            [InlineKeyboardButton(text="List tariffs", callback_data="admin_plan:list")],
            [InlineKeyboardButton(text="Default Smart price", callback_data="admin_set:price_multi_smart_per_gb")],
            [InlineKeyboardButton(text="Default Economy price", callback_data="admin_set:price_multi_economy_per_gb")],
            [InlineKeyboardButton(text="Low balance threshold", callback_data="admin_set:low_balance_threshold")],
            [InlineKeyboardButton(text="Referral cashback %", callback_data="admin_set:referral_cashback_percent")],
            [InlineKeyboardButton(text="Back", callback_data="admin:menu")],
        ]
    )


def plan_actions(plan_id: int, active: bool) -> InlineKeyboardMarkup:
    toggle_text = "Disable" if active else "Enable"
    toggle_action = "disable" if active else "enable"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Edit", callback_data=f"admin_plan_edit:{plan_id}")],
            [InlineKeyboardButton(text=toggle_text, callback_data=f"admin_plan_{toggle_action}:{plan_id}")],
            [InlineKeyboardButton(text="Delete", callback_data=f"admin_plan_delete:{plan_id}")],
            [InlineKeyboardButton(text="Back", callback_data="admin:store")],
        ]
    )


def admins_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Add admin", callback_data="admin_admin:add")],
            [InlineKeyboardButton(text="List admins", callback_data="admin_admin:list")],
            [InlineKeyboardButton(text="Back", callback_data="admin:menu")],
        ]
    )


def admin_id_actions(admin_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Remove admin", callback_data=f"admin_admin_remove:{admin_id}")],
            [InlineKeyboardButton(text="Back", callback_data="admin:admins")],
        ]
    )


def payment_settings_menu() -> InlineKeyboardMarkup:
    keys = [
        ("Card info", "card_info"),
        ("Card enabled", "payment_card_enabled"),
        ("Plisio enabled", "payment_plisio_enabled"),
        ("Plisio token", "plisio_api_token"),
        ("NOW enabled", "payment_nowpayments_enabled"),
        ("NOW token", "nowpayments_api_token"),
        ("Stars enabled", "payment_stars_enabled"),
        ("Stars rate", "stars_to_toman_rate"),
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *[[InlineKeyboardButton(text=label, callback_data=f"admin_set:{key}")] for label, key in keys],
            [InlineKeyboardButton(text="Pending receipts", callback_data="admin:receipts")],
            [InlineKeyboardButton(text="Back", callback_data="admin:menu")],
        ]
    )


def user_services_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Get user info", callback_data="admin_user:lookup")],
            [InlineKeyboardButton(text="Latest users", callback_data="admin:users")],
            [InlineKeyboardButton(text="Active/disabled services", callback_data="admin:services")],
            [InlineKeyboardButton(text="Broadcast to all", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="Back", callback_data="admin:menu")],
        ]
    )


def admin_service_actions(service_id: int, disabled: bool) -> InlineKeyboardMarkup:
    rows = []
    if disabled:
        rows.append([InlineKeyboardButton(text="Reactivate", callback_data=f"admin_svc_reactivate:{service_id}")])
    else:
        rows.append([InlineKeyboardButton(text="Disable", callback_data=f"admin_svc_disable:{service_id}")])
    rows.append([InlineKeyboardButton(text="Delete", callback_data=f"admin_svc_delete:{service_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_actions(user_id: int, blocked: bool) -> InlineKeyboardMarkup:
    text = "Unblock user" if blocked else "Block fake user"
    action = "unblock" if blocked else "block"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=f"admin_user_{action}:{user_id}")],
            [InlineKeyboardButton(text="Back", callback_data="admin:user_services")],
        ]
    )
