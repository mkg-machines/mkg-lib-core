"""Utilities für die MKG Platform.

Dieses Modul stellt Hilfsfunktionen bereit:
    - logging: Structured Logging Setup mit structlog
    - tenant: Tenant-Context-Management
    - validation: Validierungs-Utilities
    - pagination: Pagination Utilities für DynamoDB
"""

from mkg_core.utils.logging import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    unbind_context,
)
from mkg_core.utils.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MIN_LIMIT,
    PaginatedResult,
    PaginationRequest,
    PaginationResponse,
    create_paginated_result,
    create_pagination_response,
    decode_cursor,
    encode_cursor,
    paginate_list,
)
from mkg_core.utils.tenant import (
    TenantContext,
    TenantContextError,
    TenantNotSetError,
    clear_tenant_context,
    extract_tenant_from_jwt,
    get_current_tenant,
    get_current_tenant_id,
    require_current_tenant,
    require_tenant,
    set_tenant_context,
    tenant_context,
    with_tenant_context,
)
from mkg_core.utils.validation import (
    EntityId,
    ISOTimestamp,
    NonEmptyString,
    TenantId,
    UUIDString,
    extract_uuid_from_prefixed_id,
    generate_id,
    parse_uuid,
    sanitize_string,
    validate_entity_id,
    validate_iso_timestamp,
    validate_tenant_id,
    validate_uuid,
)

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MIN_LIMIT",
    "EntityId",
    "ISOTimestamp",
    "NonEmptyString",
    "PaginatedResult",
    "PaginationRequest",
    "PaginationResponse",
    "TenantContext",
    "TenantContextError",
    "TenantId",
    "TenantNotSetError",
    "UUIDString",
    "bind_context",
    "clear_context",
    "clear_tenant_context",
    "configure_logging",
    "create_paginated_result",
    "create_pagination_response",
    "decode_cursor",
    "encode_cursor",
    "extract_tenant_from_jwt",
    "extract_uuid_from_prefixed_id",
    "generate_id",
    "get_current_tenant",
    "get_current_tenant_id",
    "get_logger",
    "paginate_list",
    "parse_uuid",
    "require_current_tenant",
    "require_tenant",
    "sanitize_string",
    "set_tenant_context",
    "tenant_context",
    "unbind_context",
    "validate_entity_id",
    "validate_iso_timestamp",
    "validate_tenant_id",
    "validate_uuid",
    "with_tenant_context",
]
