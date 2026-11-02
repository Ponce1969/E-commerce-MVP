import json
from pathlib import Path

from src.infrastructure.security.audit import audit_log
from src.infrastructure.security.jwt import TokenData, UserRole


def test_audit_log_format_and_persistence():
    actor = TokenData(
        user_id=1,
        email="mariana@2rodriguez.uy",
        role=UserRole.ADMIN,
        commercial_list_id=None,
    )

    audit_log(
        action="UPDATE_PRODUCT_PRICES",
        target_entity="product",
        target_id=105,
        actor=actor,
        ip_address="192.168.1.50",
        details={"cost_iva_inc": 150.0, "price_iva_inc": 225.0},
    )

    audit_file = Path("logs/audit.log")
    assert audit_file.exists()

    with open(audit_file, encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) >= 1
        last_entry = json.loads(lines[-1].strip())

        assert last_entry["action"] == "UPDATE_PRODUCT_PRICES"
        assert last_entry["target_entity"] == "product"
        assert last_entry["target_id"] == "105"
        assert last_entry["actor_id"] == 1
        assert last_entry["actor_email"] == "mariana@2rodriguez.uy"
        assert last_entry["actor_role"] == "ADMIN"
        assert last_entry["ip_address"] == "192.168.1.50"
        assert "timestamp" in last_entry
        assert last_entry["details"]["cost_iva_inc"] == 150.0
