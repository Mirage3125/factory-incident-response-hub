import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IncidentList } from "./IncidentList";
import { jsonResponse, renderWithProviders } from "../test/render";

describe("IncidentList", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows API errors", async () => {
    vi.spyOn(window, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/incidents")) return jsonResponse({ detail: "database unavailable" }, 503);
      return jsonResponse([]);
    });

    renderWithProviders(<IncidentList />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("database unavailable"));
  });
});
