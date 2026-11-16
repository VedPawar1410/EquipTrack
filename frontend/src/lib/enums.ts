import openapi from "@/lib/api/openapi.json";

/** Enum values straight from the API contract, so dropdowns can never offer a value the API rejects. */
const schemas = openapi.components.schemas;
export const EQUIPMENT_TYPES = schemas.EquipmentType.enum as string[];
export const EQUIPMENT_STATUSES = schemas.EquipmentStatus.enum as string[];
export const SEVERITIES = schemas.Severity.enum as string[];
export const LOG_TYPES = schemas.LogType.enum as string[];
export const DOC_TYPES = schemas.DOCTYPE.enum as string[];
export const ISSUE_STATUSES = schemas.IssueStatus.enum as string[];
