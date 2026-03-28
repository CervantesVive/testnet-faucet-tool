import pytest
from handlers.base import BaseHandler, DripResult


class ConcreteHandler(BaseHandler):
    async def drip(self, address, asset_id, amount):
        return DripResult(success=True, tx_hash="0xabc", explorer_url=None, error=None, amount=amount, asset=asset_id)

    def validate_address(self, address):
        return bool(address)

    async def get_faucet_balance(self):
        return {"ETH": "1.0"}

    def supported_assets(self):
        return ["TEST"]


def test_drip_result_fields():
    r = DripResult(success=True, tx_hash="0x1", explorer_url="http://x", error=None, amount="1.0", asset="HTETH")
    assert r.success
    assert r.tx_hash == "0x1"


def test_concrete_handler_validate():
    h = ConcreteHandler(config={})
    assert h.validate_address("0xabc")
    assert not h.validate_address("")


@pytest.mark.asyncio
async def test_concrete_handler_drip():
    h = ConcreteHandler(config={})
    result = await h.drip("0xabc", "TEST", "1.0")
    assert result.success
    assert result.asset == "TEST"
