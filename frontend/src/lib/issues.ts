import type { Schemas } from "@/lib/api/client";
import type { Role } from "@/lib/auth";

type IssueStatus = Schemas["IssueStatus"];

/**
 * Mirror of the API's issue lifecycle (app/services/issue_service.py TRANSITIONS), used only to decide
 * which buttons to show. The API enforces the same table on every request.
 */
export const TRANSITIONS: { from: IssueStatus; to: IssueStatus; label: string; minRole: Role }[] = [
  { from: "Open", to: "In Progress", label: "Claim", minRole: "technician" },
  { from: "In Progress", to: "Resolved", label: "Mark resolved", minRole: "technician" },
  { from: "Resolved", to: "Closed", label: "Close", minRole: "supervisor" },
  { from: "Resolved", to: "In Progress", label: "Reopen", minRole: "supervisor" },
];

export const BOARD_COLUMNS: IssueStatus[] = ["Open", "In Progress", "Resolved", "Closed"];
