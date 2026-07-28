from app.models.user import UserRole

from .conftest import auth_headers_for_user, seed_application, seed_user


def test_customer_is_blocked_from_review_and_admin_routes(client, fake_database):
    customer = seed_user(
        fake_database,
        role=UserRole.CUSTOMER,
        email="rbac.customer@example.com",
        phone="9800000500",
    )
    application = seed_application(fake_database, applicant_id=str(customer["_id"]))
    headers = auth_headers_for_user(customer)

    protected_requests = [
        ("post", f"/risk/calculate/{application['_id']}"),
        ("post", f"/flags/check/{application['_id']}"),
        ("get", "/officer/applications"),
        ("get", "/admin/users"),
    ]

    for method, path in protected_requests:
        response = getattr(client, method)(path, headers=headers)
        assert response.status_code == 403


def test_officer_is_blocked_from_admin_routes(client, fake_database):
    officer = seed_user(
        fake_database,
        role=UserRole.OFFICER,
        email="rbac.officer@example.com",
        phone="9800000510",
    )

    response = client.get("/admin/users", headers=auth_headers_for_user(officer))

    assert response.status_code == 403


def test_admin_is_blocked_from_officer_only_routes(client, fake_database):
    admin = seed_user(
        fake_database,
        role=UserRole.ADMIN,
        email="rbac.admin@example.com",
        phone="9800000520",
    )

    response = client.get("/officer/applications", headers=auth_headers_for_user(admin))

    assert response.status_code == 403
