from aiohttp import ClientSession, ClientTimeout


class PaymentProviderError(RuntimeError):
    pass


class PlisioClient:
    def __init__(self, api_token: str):
        self.api_token = api_token

    async def create_invoice(self, amount_toman: int, order_id: str) -> tuple[str, str]:
        async with ClientSession(timeout=ClientTimeout(total=30)) as session:
            params = {"api_key": self.api_token, "order_number": order_id, "amount": amount_toman, "currency": "IRT"}
            async with session.get("https://plisio.net/api/v1/invoices/new", params=params) as response:
                data = await response.json()
        if data.get("status") != "success":
            raise PaymentProviderError(str(data))
        invoice = data["data"]
        return str(invoice["txn_id"]), str(invoice["invoice_url"])

    async def is_paid(self, invoice_id: str) -> bool:
        async with ClientSession(timeout=ClientTimeout(total=30)) as session:
            params = {"api_key": self.api_token, "txn_id": invoice_id}
            async with session.get("https://plisio.net/api/v1/operations/" + invoice_id, params=params) as response:
                data = await response.json()
        status = data.get("data", {}).get("status")
        return status in {"completed", "mismatch"}


class NowPaymentsClient:
    def __init__(self, api_token: str):
        self.api_token = api_token

    async def create_invoice(self, amount_toman: int, order_id: str) -> tuple[str, str]:
        headers = {"x-api-key": self.api_token}
        payload = {"price_amount": amount_toman, "price_currency": "irt", "order_id": order_id}
        async with ClientSession(timeout=ClientTimeout(total=30)) as session:
            async with session.post("https://api.nowpayments.io/v1/invoice", headers=headers, json=payload) as response:
                data = await response.json()
        if "id" not in data:
            raise PaymentProviderError(str(data))
        return str(data["id"]), str(data["invoice_url"])

    async def is_paid(self, invoice_id: str) -> bool:
        headers = {"x-api-key": self.api_token}
        async with ClientSession(timeout=ClientTimeout(total=30)) as session:
            async with session.get(f"https://api.nowpayments.io/v1/payment/{invoice_id}", headers=headers) as response:
                data = await response.json()
        return data.get("payment_status") in {"finished", "confirmed"}

