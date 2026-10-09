from django.urls import path

from .views import resource_list

urlpatterns = [
    path("hr/departments", resource_list, {"resource": "departments"}),
    path("hr/employees", resource_list, {"resource": "employees"}),
    path("hr/leave-balances", resource_list, {"resource": "leave-balances"}),
    path("assets/items", resource_list, {"resource": "assets"}),
    path("assets/loans", resource_list, {"resource": "asset-loans"}),
    path("facilities/resources", resource_list, {"resource": "facilities"}),
    path("crm/customers", resource_list, {"resource": "customers"}),
    path("crm/contracts", resource_list, {"resource": "contracts"}),
    path("procurement/suppliers", resource_list, {"resource": "suppliers"}),
    path("procurement/catalog-items", resource_list, {"resource": "catalog-items"}),
    path("it/applications", resource_list, {"resource": "applications"}),
    path("it/access-roles", resource_list, {"resource": "access-roles"}),
    path("it/services", resource_list, {"resource": "it-services"}),
    path("finance/budgets", resource_list, {"resource": "budgets"}),
    path(
        "finance/expense-categories", resource_list, {"resource": "expense-categories"}
    ),
    path("travel/policies", resource_list, {"resource": "travel-policies"}),
    path("travel/options", resource_list, {"resource": "travel-options"}),
]
