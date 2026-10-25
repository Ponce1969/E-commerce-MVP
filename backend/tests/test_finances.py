from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from src.domain.services.financial_service import FinancialService
from src.main import app


def test_financial_service_calculations() -> None:
    # 1. COGS with known unit cost
    cogs_direct = FinancialService.calculate_cogs(
        unit_cost=Decimal("100.50"),
        unit_price=Decimal("150.00"),
        markup_percentage=Decimal("49.2537"),
        quantity=3,
    )
    assert cogs_direct == Decimal("301.50")

    # 2. COGS deduced from markup percentage: price 150, markup 50% -> cost 100
    cogs_deduced = FinancialService.calculate_cogs(
        unit_cost=None,
        unit_price=Decimal("150.00"),
        markup_percentage=Decimal("50.00"),
        quantity=2,
    )
    assert cogs_deduced == Decimal("200.00")

    # 3. Gross Margin: 300 - 200 = 100
    gross_margin = FinancialService.calculate_gross_margin(
        gross_revenue=Decimal("300.00"), cogs=Decimal("200.00")
    )
    assert gross_margin == Decimal("100.00")

    # 4. Net Profit: 100 margin - 40 expenses = 60
    net_profit = FinancialService.calculate_net_profit(
        gross_margin=gross_margin, total_expenses=Decimal("40.00")
    )
    assert net_profit == Decimal("60.00")

    # 5. Margin Percentage: (100 / 300) * 100 = 33.33%
    margin_pct = FinancialService.calculate_margin_percentage(
        gross_margin=gross_margin, gross_revenue=Decimal("300.00")
    )
    assert margin_pct == Decimal("33.33")


@pytest.mark.asyncio
async def test_finances_api_endpoints() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Admin Login
        admin_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "mariana@2rodriguez.uy", "password": "Admin2Rodriguez!2026"},
        )
        assert admin_res.status_code == 200
        admin_token = admin_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. Record an operational expense (e.g. Alquiler de depósito Paso Molino)
        today_iso = date.today().isoformat()
        exp_res = await client.post(
            "/api/v1/admin/finances/expenses",
            json={
                "category": "Alquiler Depósito",
                "description": "Alquiler mensual Paso Molino",
                "expense_date": today_iso,
                "amount": "12500.00",
            },
            headers=headers,
        )
        assert exp_res.status_code == 201
        exp_data = exp_res.json()
        assert exp_data["category"] == "Alquiler Depósito"
        assert Decimal(str(exp_data["amount"])) == Decimal("12500.00")
        exp_id = exp_data["id"]

        # 2. Record another expense (Packaging)
        exp_pkg = await client.post(
            "/api/v1/admin/finances/expenses",
            json={
                "category": "Packaging",
                "description": "Bidones 5L y cajas de cartón",
                "expense_date": today_iso,
                "amount": "1500.00",
            },
            headers=headers,
        )
        assert exp_pkg.status_code == 201

        # 3. List expenses
        list_res = await client.get("/api/v1/admin/finances/expenses", headers=headers)
        assert list_res.status_code == 200
        expenses_list = list_res.json()
        assert any(e["id"] == exp_id for e in expenses_list)

        # 4. Get Financial Summary
        summary_res = await client.get("/api/v1/admin/finances/summary", headers=headers)
        assert summary_res.status_code == 200
        summary_data = summary_res.json()
        assert Decimal(str(summary_data["total_expenses"])) >= Decimal("14000.00")
        assert "gross_revenue" in summary_data
        assert "gross_margin" in summary_data
        assert "net_profit" in summary_data
        assert len(summary_data["monthly_trend"]) == 6

        # 5. Delete temporary expense
        del_res = await client.delete(f"/api/v1/admin/finances/expenses/{exp_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True
