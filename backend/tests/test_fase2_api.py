from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.infrastructure.db.models import CommercialListORM, CustomerORM
from src.infrastructure.db.session import async_session_factory
from src.infrastructure.security.password import hash_password
from src.main import app


@pytest.mark.asyncio
async def test_auth_and_admin_portal_workflows() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test Admin Login Success
        admin_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "mariana@2rodriguez.uy", "password": "Admin2Rodriguez!2026"},
        )
        assert admin_res.status_code == 200
        admin_data = admin_res.json()
        assert admin_data["role"] == "ADMIN"
        assert "access_token" in admin_data
        admin_token = admin_data["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Test Invalid Password
        wrong_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "mariana@2rodriguez.uy", "password": "wrong_password"},
        )
        assert wrong_res.status_code == 401

        # 3. Test Admin Product Listing & Filter by Conflict (Exact 19 historical conflicts)
        conflicts_res = await client.get(
            "/api/v1/admin/products?has_conflict=true&limit=100", headers=admin_headers
        )
        assert conflicts_res.status_code == 200
        assert len(conflicts_res.json()) == 19

        # 4. Test Incomplete Draft Publishing Restriction (Rule UC-ADM-05)
        new_prod_res = await client.post(
            "/api/v1/admin/products",
            json={
                "name": "Detergente Test Validacion",
                "presentation": "5 L",
                "provider": "Moizo",
                "category": "Limpieza",
            },
            headers=admin_headers,
        )
        assert new_prod_res.status_code == 201
        created_id = new_prod_res.json()["id"]

        # Try to publish incomplete draft -> must fail with 400
        publish_fail = await client.patch(
            f"/api/v1/admin/products/{created_id}/publish",
            json={"is_published": True},
            headers=admin_headers,
        )
        assert publish_fail.status_code == 400
        assert "requiere al menos una lista con costo y recargo" in publish_fail.json()["detail"]

        # Update prices for lista 1 (cost 100, markup 50% -> price 150)
        update_price_res = await client.put(
            f"/api/v1/admin/products/{created_id}/prices",
            json={
                "prices": [
                    {
                        "commercial_list_id": 1,
                        "cost_iva_inc": 100.0,
                        "markup_percentage": 50.0,
                    }
                ]
            },
            headers=admin_headers,
        )
        assert update_price_res.status_code == 200
        assert Decimal(str(update_price_res.json()[0]["price_iva_inc"])) == Decimal("150.00")

        # Now publishing must succeed
        publish_ok = await client.patch(
            f"/api/v1/admin/products/{created_id}/publish",
            json={"is_published": True},
            headers=admin_headers,
        )
        assert publish_ok.status_code == 200
        assert publish_ok.json()["is_published"] is True

        # 4.1 Update Product Stock & Inventory Thresholds
        stock_update_res = await client.put(
            f"/api/v1/admin/products/{created_id}/stock",
            json={"current_stock": 10, "min_stock_alert": 5, "allow_backorder": False},
            headers=admin_headers,
        )
        assert stock_update_res.status_code == 200
        stock_data = stock_update_res.json()
        assert stock_data["current_stock"] == 10
        assert stock_data["min_stock_alert"] == 5
        assert stock_data["is_low_stock"] is False
        assert stock_data["is_out_of_stock"] is False

        # Filter products by low stock (stock <= min_stock_alert)
        low_stock_res = await client.get(
            "/api/v1/admin/products?stock_status=low&limit=10",
            headers=admin_headers,
        )
        assert low_stock_res.status_code == 200
        assert all(p["current_stock"] <= p["min_stock_alert"] for p in low_stock_res.json())

        # 5. Test Quote PDF Generation
        pdf_res = await client.post(
            "/api/v1/admin/quotes/pdf",
            json={
                "commercial_list_id": 1,
                "client_name": "Hospital Britanico",
                "client_phone": "099 123 456",
                "items": [
                    {
                        "product_id": created_id,
                        "quantity": 4,
                        "discount_percentage": 10.0,
                    }
                ],
            },
            headers=admin_headers,
        )
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert pdf_res.content.startswith(b"%PDF")

        # 6. Ensure Test B2B Customer in Database
        async with async_session_factory() as session:
            list_stmt = select(CommercialListORM).limit(1)
            list_obj = (await session.execute(list_stmt)).scalar_one()

            cust_stmt = select(CustomerORM).where(CustomerORM.email == "empresa@cliente.uy")
            existing_cust = (await session.execute(cust_stmt)).scalar_one_or_none()
            if not existing_cust:
                test_customer = CustomerORM(
                    document_type="RUT",
                    document_number="219998880011",
                    business_name="Empresa Limpieza Test",
                    contact_name="Juan Perez",
                    phone_whatsapp="099888777",
                    email="empresa@cliente.uy",
                    password_hash=hash_password("ClienteB2B!2026"),
                    commercial_list_id=list_obj.id,
                    crm_status="ACTIVO",
                    is_active=True,
                )
                session.add(test_customer)
                await session.commit()

        # 7. Customer Login
        cust_login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "empresa@cliente.uy", "password": "ClienteB2B!2026"},
        )
        assert cust_login_res.status_code == 200
        cust_token = cust_login_res.json()["access_token"]
        cust_headers = {"Authorization": f"Bearer {cust_token}"}

        # Customer tries to access admin route -> forbidden 403
        forbidden_res = await client.get("/api/v1/admin/products", headers=cust_headers)
        assert forbidden_res.status_code == 403

        # 8. Customer Portal Catalog (Must see published product, strictly hiding costs/suppliers)
        portal_catalog_res = await client.get("/api/v1/portal/catalog", headers=cust_headers)
        assert portal_catalog_res.status_code == 200
        items = portal_catalog_res.json()
        assert any(it["id"] == created_id for it in items)
        portal_item = next(it for it in items if it["id"] == created_id)
        assert "provider" not in portal_item
        assert "cost_iva_inc" not in portal_item
        assert "markup_percentage" not in portal_item

        # 8.1 Customer Order Rejection when Stock is Insufficient
        insufficient_stock_res = await client.post(
            "/api/v1/portal/orders",
            json={
                "delivery_type": "PICKUP_PASO_MOLINO",
                "items": [{"product_id": created_id, "quantity": 999}],
            },
            headers=cust_headers,
        )
        assert insufficient_stock_res.status_code == 400
        assert "Stock insuficiente" in insufficient_stock_res.json()["detail"]

        # 9. Customer Order Creation - Retiro en Paso Molino (Costo 0)
        order_pickup_res = await client.post(
            "/api/v1/portal/orders",
            json={
                "delivery_type": "PICKUP_PASO_MOLINO",
                "delivery_notes": "Retira Mariana por la mañana",
                "items": [{"product_id": created_id, "quantity": 2}],
            },
            headers=cust_headers,
        )
        assert order_pickup_res.status_code == 201
        order_data = order_pickup_res.json()
        assert Decimal(str(order_data["delivery_cost"])) == Decimal("0.00")
        assert Decimal(str(order_data["total_amount"])) == Decimal("300.00")  # 2 * 150

        # 10. Customer Order Creation - Cadetería Marco Postal (Costo 250)
        order_cadeteria_res = await client.post(
            "/api/v1/portal/orders",
            json={
                "delivery_type": "CADETERIA_MARCO_POSTAL",
                "delivery_address": "Av. Agraciada 2850, Montevideo",
                "delivery_notes": "Tercer piso timbre 301",
                "items": [{"product_id": created_id, "quantity": 1}],
            },
            headers=cust_headers,
        )
        assert order_cadeteria_res.status_code == 201
        cad_data = order_cadeteria_res.json()
        assert Decimal(str(cad_data["delivery_cost"])) == Decimal("250.00")
        assert Decimal(str(cad_data["total_amount"])) == Decimal("400.00")  # 150 + 250

        # 11. Verify Stock Deduction in Admin (Started with 10, deducted 2 + 1 = 7)
        admin_stock_check = await client.get(
            "/api/v1/admin/products?search=Detergente Test Validacion",
            headers=admin_headers,
        )
        assert admin_stock_check.status_code == 200
        checked_prod = next(p for p in admin_stock_check.json() if p["id"] == created_id)
        assert checked_prod["current_stock"] == 7

        # 12. Test Provider Secrecy in Admin vs Portal & Provider List Endpoint
        prov_res = await client.get("/api/v1/admin/providers", headers=admin_headers)
        assert prov_res.status_code == 200
        assert "Moizo" in prov_res.json()

        # 13. Test Inventory CSV Export (Excel Compatible with UTF-8-SIG)
        export_res = await client.get("/api/v1/admin/inventory/export", headers=admin_headers)
        assert export_res.status_code == 200
        assert export_res.headers["content-type"].startswith("text/csv")
        assert b"Stock Actual" in export_res.content

        # 14. Test Inventory CSV Import (Update stock to 45 with backorder True)
        csv_payload = (
            f"ID;Codigo;Nombre;Presentacion;Proveedor;Categoria;Stock Actual;Alerta Minima;Permitir Backorder\n"
            f"{created_id};;Detergente Test Validacion;;;;45;12;SI\n"
        )
        import_res = await client.post(
            "/api/v1/admin/inventory/import",
            files={"file": ("inventario.csv", csv_payload.encode("utf-8-sig"), "text/csv")},
            headers=admin_headers,
        )
        assert import_res.status_code == 200
        assert import_res.json()["updated_count"] == 1

        # 15. Test Attachments (Image and Technical Sheet PDF Upload)
        img_res = await client.post(
            "/api/v1/admin/attachments",
            data={"product_id": str(created_id), "attachment_type": "image"},
            files={"file": ("foto_producto.png", b"fake_png_binary_data", "image/png")},
            headers=admin_headers,
        )
        assert img_res.status_code == 200
        assert img_res.json()["url"].startswith("/static/uploads/images/")

        pdf_doc_res = await client.post(
            "/api/v1/admin/attachments",
            data={"product_id": str(created_id), "attachment_type": "tech_sheet"},
            files={"file": ("ficha_limpieza.pdf", b"%PDF-1.4 fake_pdf_data", "application/pdf")},
            headers=admin_headers,
        )
        assert pdf_doc_res.status_code == 200
        assert pdf_doc_res.json()["url"].startswith("/static/uploads/documents/")
