"""URLconf of the Mock Systems service (EAS_SERVICE=mock)."""

from django.urls import path

from . import api

urlpatterns = [
    path("mock-api/v1/health", api.health),
    path("mock-api/v1/hr/departments", api.hr_departments),
    path("mock-api/v1/hr/employees", api.hr_employees),
    path("mock-api/v1/hr/leave-balances", api.hr_leave_balances),
    path("mock-api/v1/hr/leave-usages", api.hr_leave_usages),
    path("mock-api/v1/assets/categories", api.asset_categories),
    path(
        "mock-api/v1/assets/categories/<str:code>/availability", api.asset_availability
    ),
    path("mock-api/v1/assets/loans", api.asset_loans),
    path("mock-api/v1/facilities/resources", api.facility_resources),
    path(
        "mock-api/v1/facilities/resources/<str:code>/availability",
        api.facility_availability,
    ),
    path("mock-api/v1/facilities/reservations", api.facility_reservations),
    path("mock-api/v1/allocations", api.allocations),
    path("mock-api/v1/allocations/<str:action>", api.allocation_action),
    path("mock-api/v1/it/applications", api.it_applications),
    path("mock-api/v1/it/access-roles", api.it_access_roles),
    path("mock-api/v1/it/user-access", api.it_user_access),
    path("mock-api/v1/finance/expense-categories", api.finance_expense_categories),
    path("mock-api/v1/finance/budgets", api.finance_budgets),
    path("mock-api/v1/finance/commitments", api.finance_commitments),
    path("mock-api/v1/catalogue/<str:resource>", api.catalogue),
]
