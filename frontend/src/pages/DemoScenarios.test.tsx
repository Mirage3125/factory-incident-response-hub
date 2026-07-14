import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DemoScenarios } from "./DemoScenarios";
import { jsonResponse, renderWithProviders } from "../test/render";

describe("DemoScenarios", () => {
  afterEach(() => vi.restoreAllMocks());

  it("triggers a real backend scenario flow from the page", async () => {
    vi.spyOn(window, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/api/demo/scenarios")) return jsonResponse([{ code: "cnc-vibration-p1", name: "CNC", equipment_code: "CNC-01", incident_type: "vibration", severity: "P1" }]);
      if (url.includes("/api/demo/scenarios/cnc-vibration-p1/trigger") && init?.method === "POST") {
        return jsonResponse({ duplicate: false, original_incident_id: null, incident: { id: 4, incident_no: "INC-4", equipment_id: 1, production_batch_id: null, incident_type: "vibration", title: "CNC", description: "desc", severity: "P1", status: "RECEIVED", occurrence_count: 1, first_seen_at: new Date().toISOString(), last_seen_at: new Date().toISOString(), sla_due_at: new Date().toISOString() } });
      }
      if (url.includes("/analyze")) return jsonResponse({ incident_id: 4, analysis_run_id: 1, provider: "demo", model: "demo-analyzer", prompt_version: "v1", fallback_used: false, final_severity: "P1", requires_human_approval: true, agent_output: { summary: "summary", probable_causes: [], recommended_actions: [], missing_information: [], risk_level: "P1", confidence: 0.9, requires_human_approval: true }, rule_reasons: [] });
      if (url.includes("/api/incidents") || url.includes("/api/work-orders") || url.includes("/api/rpa-runs") || url.includes("/recent-incidents")) return jsonResponse([]);
      return jsonResponse({});
    });

    renderWithProviders(<DemoScenarios />);
    await userEvent.click(await screen.findByRole("button", { name: /主轴振动严重异常/i }));

    await waitFor(() => expect(screen.getByText("INC-4")).toBeInTheDocument());
  });
});
