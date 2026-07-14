import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Dashboard } from "./Dashboard";
import { jsonResponse, renderWithProviders } from "../test/render";

describe("Dashboard", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders live dashboard metrics", async () => {
    vi.spyOn(window, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/summary")) return jsonResponse({ total_incidents: 2, open_incidents: 1, total_work_orders: 3, pending_approvals: 1 });
      if (url.includes("/severity-distribution")) return jsonResponse([{ severity: "P1", count: 1 }, { severity: "P2", count: 1 }]);
      if (url.includes("/recent-incidents")) {
        return jsonResponse([
          {
            id: 1,
            incident_no: "INC-1",
            equipment_id: 1,
            production_batch_id: null,
            incident_type: "vibration",
            title: "Spindle vibration",
            description: "value high",
            severity: "P1",
            status: "AWAITING_APPROVAL",
            occurrence_count: 1,
            first_seen_at: new Date().toISOString(),
            last_seen_at: new Date().toISOString(),
            sla_due_at: new Date().toISOString()
          }
        ]);
      }
      if (url.includes("/sla-metrics")) return jsonResponse({ overdue_work_orders: 1, due_soon_work_orders: 0, overdue_incidents: 0 });
      if (url.includes("/work-orders")) return jsonResponse([]);
      if (url.includes("/approvals/pending")) return jsonResponse([]);
      return jsonResponse({});
    });

    renderWithProviders(<Dashboard />);

    await waitFor(() => expect(screen.getByText("Spindle vibration")).toBeInTheDocument());
    expect(screen.getByText("高优先级异常")).toBeInTheDocument();
  });
});
