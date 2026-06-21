from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="داشبورد", callback_data="admin:dashboard")],
            [InlineKeyboardButton(text="مدیریت پنل‌ها", callback_data="admin:panels")],
            [InlineKeyboardButton(text="تنظیمات فروشگاه", callback_data="admin:store")],
            [InlineKeyboardButton(text="تنظیمات ادمین‌ها", callback_data="admin:admins")],
            [InlineKeyboardButton(text="تنظیمات پرداخت", callback_data="admin:payment_settings")],
            [InlineKeyboardButton(text="خدمات کاربر", callback_data="admin:user_services")],
        ]
    )


def receipt_review(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="تایید", callback_data=f"admin_receipt_ok:{payment_id}"),
                InlineKeyboardButton(text="رد", callback_data=f"admin_receipt_no:{payment_id}"),
            ]
        ]
    )


def admin_back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="بازگشت به مدیریت", callback_data="admin:menu")]]
    )


def panels_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="افزودن پنل PasarGuard", callback_data="admin_panel:add")],
            [InlineKeyboardButton(text="لیست پنل‌ها", callback_data="admin_panel:list")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:menu")],
        ]
    )


def panel_actions(panel_id: int, active: bool) -> InlineKeyboardMarkup:
    toggle_text = "غیرفعال کردن" if active else "فعال کردن"
    toggle_action = "disable" if active else "enable"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ویرایش", callback_data=f"admin_panel_edit:{panel_id}")],
            [InlineKeyboardButton(text="افزودن تمپلیت", callback_data=f"admin_template_add:{panel_id}")],
            [InlineKeyboardButton(text="لیست تمپلیت‌ها", callback_data=f"admin_template_list:{panel_id}")],
            [InlineKeyboardButton(text=toggle_text, callback_data=f"admin_panel_{toggle_action}:{panel_id}")],
            [InlineKeyboardButton(text="حذف", callback_data=f"admin_panel_delete:{panel_id}")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:panels")],
        ]
    )


def panel_list_actions(panel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="مشاهده و مدیریت", callback_data=f"admin_panel_view:{panel_id}")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:panels")],
        ]
    )


def panels_list_keyboard(panels) -> InlineKeyboardMarkup:
    rows = []
    for panel in panels:
        rows.append([InlineKeyboardButton(text=f"{panel.name} #{panel.id}", callback_data=f"admin_panel_view:{panel.id}")])
        rows.append(
            [
                InlineKeyboardButton(text="ویرایش", callback_data=f"admin_panel_edit:{panel.id}"),
                InlineKeyboardButton(text="افزودن تمپلیت", callback_data=f"admin_template_add:{panel.id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="بازگشت", callback_data="admin:panels")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def store_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="افزودن تعرفه", callback_data="admin_plan:add")],
            [InlineKeyboardButton(text="لیست تعرفه‌ها", callback_data="admin_plan:list")],
            [InlineKeyboardButton(text="قیمت پیش‌فرض هوشمند", callback_data="admin_set:price_multi_smart_per_gb")],
            [InlineKeyboardButton(text="قیمت پیش‌فرض اقتصادی", callback_data="admin_set:price_multi_economy_per_gb")],
            [InlineKeyboardButton(text="حد هشدار کمبود موجودی", callback_data="admin_set:low_balance_threshold")],
            [InlineKeyboardButton(text="درصد کش‌بک معرفی", callback_data="admin_set:referral_cashback_percent")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:menu")],
        ]
    )


def plan_actions(plan_id: int, active: bool) -> InlineKeyboardMarkup:
    toggle_text = "غیرفعال کردن" if active else "فعال کردن"
    toggle_action = "disable" if active else "enable"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ویرایش", callback_data=f"admin_plan_edit:{plan_id}")],
            [InlineKeyboardButton(text=toggle_text, callback_data=f"admin_plan_{toggle_action}:{plan_id}")],
            [InlineKeyboardButton(text="حذف", callback_data=f"admin_plan_delete:{plan_id}")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:store")],
        ]
    )


def admins_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="افزودن ادمین", callback_data="admin_admin:add")],
            [InlineKeyboardButton(text="لیست ادمین‌ها", callback_data="admin_admin:list")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:menu")],
        ]
    )


def admin_id_actions(admin_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="حذف ادمین", callback_data=f"admin_admin_remove:{admin_id}")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:admins")],
        ]
    )


def payment_settings_menu() -> InlineKeyboardMarkup:
    keys = [
        ("اطلاعات کارت", "card_info"),
        ("وضعیت کارت به کارت", "payment_card_enabled"),
        ("وضعیت Plisio", "payment_plisio_enabled"),
        ("توکن Plisio", "plisio_api_token"),
        ("وضعیت NOWPayments", "payment_nowpayments_enabled"),
        ("توکن NOWPayments", "nowpayments_api_token"),
        ("وضعیت استارز", "payment_stars_enabled"),
        ("نرخ هر استار", "stars_to_toman_rate"),
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *[[InlineKeyboardButton(text=label, callback_data=f"admin_set:{key}")] for label, key in keys],
            [InlineKeyboardButton(text="رسیدهای در انتظار", callback_data="admin:receipts")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:menu")],
        ]
    )


def user_services_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="دریافت اطلاعات کاربر", callback_data="admin_user:lookup")],
            [InlineKeyboardButton(text="آخرین کاربران", callback_data="admin:users")],
            [InlineKeyboardButton(text="سرویس‌های فعال/غیرفعال", callback_data="admin:services")],
            [InlineKeyboardButton(text="ارسال پیام همگانی", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:menu")],
        ]
    )


def admin_service_actions(service_id: int, disabled: bool) -> InlineKeyboardMarkup:
    rows = []
    if disabled:
        rows.append([InlineKeyboardButton(text="فعال‌سازی مجدد", callback_data=f"admin_svc_reactivate:{service_id}")])
    else:
        rows.append([InlineKeyboardButton(text="غیرفعال کردن", callback_data=f"admin_svc_disable:{service_id}")])
    rows.append([InlineKeyboardButton(text="حذف", callback_data=f"admin_svc_delete:{service_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_actions(user_id: int, blocked: bool) -> InlineKeyboardMarkup:
    text = "رفع مسدودی کاربر" if blocked else "مسدود کردن کاربر فیک"
    action = "unblock" if blocked else "block"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=f"admin_user_{action}:{user_id}")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin:user_services")],
        ]
    )
