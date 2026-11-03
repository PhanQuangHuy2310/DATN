from django.urls import path

from .analytics import admin_analytics_view
from .apis_and_versions import (
    mock_api_toggle_circuit_breaker,
    mock_apis_list_view,
    public_circuit_breaker_status,
    system_versions_changelog_view,
)
from .org_users_rbac import (
    org_chart_tree_view,
    rbac_matrix_view,
    rbac_role_permission_update,
    rbac_roles_list,
    rbac_user_permission_reset,
    rbac_user_permission_update,
    rbac_user_permissions_view,
    user_leave_trip_manage,
    user_management_detail,
    user_requests_detail_view,
    users_management_list,
)
from .overview import system_diagnostics, system_overview
from .regulations_ai import (
    ai_engine_test_view,
    ai_retrain_trigger,
    ai_system_state_view,
    public_ai_status_view,
    regulation_detail_update_delete,
    regulations_list_create,
)
from .views import access_matrix_view, api_catalog_view, records
from .workflows import (
    request_template_detail,
    request_templates_list,
    workflow_categories_list,
    workflow_category_detail,
)

urlpatterns = [
    path("overview", system_overview, name="admin-overview"),
    path("analytics", admin_analytics_view, name="admin-analytics"),
    path("diagnostics", system_diagnostics, name="admin-diagnostics"),
    path("api-catalog", api_catalog_view, name="admin-api-catalog"),
    path("access-matrix", access_matrix_view, name="admin-access-matrix"),
    path(
        "workflow-categories",
        workflow_categories_list,
        name="admin-workflow-categories",
    ),
    path(
        "workflow-categories/<str:code>",
        workflow_category_detail,
        name="admin-workflow-category-detail",
    ),
    path("request-templates", request_templates_list, name="admin-request-templates"),
    path(
        "request-templates/<uuid:template_id>",
        request_template_detail,
        name="admin-request-template-detail",
    ),
    path("mock-apis", mock_apis_list_view, name="admin-mock-apis"),
    # Phase 4: Org Chart, Users Management & RBAC Matrix
    path("org-chart-tree", org_chart_tree_view, name="admin-org-chart-tree"),
    path("users-management", users_management_list, name="admin-users-management"),
    path(
        "users-management/<uuid:user_id>",
        user_management_detail,
        name="admin-user-management-detail",
    ),
    path(
        "users-management/<uuid:user_id>/requests-detail",
        user_requests_detail_view,
        name="admin-user-requests-detail",
    ),
    path(
        "users-management/<uuid:user_id>/leave-trip",
        user_leave_trip_manage,
        name="admin-user-leave-trip",
    ),
    path("rbac/roles", rbac_roles_list, name="admin-rbac-roles"),
    path("rbac/matrix", rbac_matrix_view, name="admin-rbac-matrix"),
    path(
        "rbac/role-permission",
        rbac_role_permission_update,
        name="admin-rbac-role-permission-update",
    ),
    path(
        "rbac/user-permissions/<uuid:user_id>",
        rbac_user_permissions_view,
        name="admin-rbac-user-permissions",
    ),
    path(
        "rbac/user-permission",
        rbac_user_permission_update,
        name="admin-rbac-user-permission-update",
    ),
    path(
        "rbac/user-permission/<uuid:user_id>/reset",
        rbac_user_permission_reset,
        name="admin-rbac-user-permission-reset",
    ),
    # Phase 5: Regulations & AI Engine Management
    path("regulations", regulations_list_create, name="admin-regulations"),
    path(
        "regulations/<uuid:reg_id>",
        regulation_detail_update_delete,
        name="admin-regulation-detail",
    ),
    path("ai-engine/status", ai_system_state_view, name="admin-ai-engine-status"),
    path("ai-engine/retrain", ai_retrain_trigger, name="admin-ai-engine-retrain"),
    path("ai-engine/test", ai_engine_test_view, name="admin-ai-engine-test"),
    path("ai-status", public_ai_status_view, name="admin-ai-status"),
    # Phase 6: Mock API Management (Circuit Breaker) & System Versions Changelog
    path("mock-apis/list", mock_apis_list_view, name="admin-mock-apis-full"),
    path(
        "mock-apis/<uuid:api_id>/toggle",
        mock_api_toggle_circuit_breaker,
        name="admin-mock-api-toggle",
    ),
    path(
        "system-versions/changelog",
        system_versions_changelog_view,
        name="admin-system-versions-changelog",
    ),
    path(
        "api-circuit-breaker-status",
        public_circuit_breaker_status,
        name="admin-api-circuit-breaker-status",
    ),
    path("<str:kind>", records),
    path("<str:kind>/<uuid:record_id>", records),
]
