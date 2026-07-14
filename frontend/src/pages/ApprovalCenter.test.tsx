import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApprovalCenter } from "./ApprovalCenter";
import { jsonResponse, renderWithProviders } from "../test/render";

describe("ApprovalCenter", () => {
  afterEach(() => vi.restoreAllMocks());

  it("prevents duplicate approval submits while a request is pending", async () => {
    const fetchMock = vi.spyOn(window, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/approvals/pending")) return jsonResponse([{ id: 1, incident_id: 1, status: "PENDING", approver: null, comment: null, decided_at: null, created_at: new Date().toISOString() }]);
      if (url.includes("/api/incidents")) {
        return jsonResponse([{ id: 1, incident_no: "INC-1", equipment_id: 1, production_batch_id: null, incident_type: "vibration", title: "Approval incident", description: "desc", severity: "P1", status: "AWAITING_APPROVAL", occurrence_count: 1, first_seen_at: new Date().toISOString(), last_seen_at: new Date().toISOString(), sla_due_at: new Date().toISOString() }]);
      }
      if (url.includes("/approve") && init?.method === "POST") return new Promise((resolve) => setTimeout(() => resolve(new Response(JSON.stringify({ id: 1, incident_id: 1, status: "APPROVED", approver: "frontend-operator", comment: "", decided_at: new Date().toISOString(), created_at: new Date().toISOString() }), { status: 200 })), 50));
      return jsonResponse({});
    });

    renderWithProviders(<ApprovalCenter />);
    const button = await screen.findByRole("button", { name: /批准/i });
    await userEvent.dblClick(button);

    await waitFor(() => expect(fetchMock.mock.calls.filter((call) => String(call[0]).includes("/approve")).length).toBe(1));
  });
});
