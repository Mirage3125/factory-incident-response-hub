import { describe, expect, it } from "vitest";
import {
  displayBoolean,
  displayCreationMethod,
  displayIncidentStatus,
  displaySeverity,
  displayWorkOrderStatus,
  formatDateTime,
  formatDurationMinutes,
  formatErrorMessage,
  nextWorkOrderAction,
  severityClass
} from "./format";

describe("format helpers", () => {
  it("formats durations and classifies severity", () => {
    expect(formatDurationMinutes(75)).toBe("1h 15m");
    expect(severityClass("P1")).toContain("red");
  });

  it("formats date and time in Chinese-friendly 24-hour format", () => {
    expect(formatDateTime("2026-07-14T08:37:22+08:00")).toBe("2026-07-14 08:37");
  });

  it("maps backend values to user-facing Chinese labels", () => {
    expect(displaySeverity("P1")).toBe("P1 严重");
    expect(displaySeverity("P2")).toBe("P2 高");
    expect(displayIncidentStatus("AWAITING_APPROVAL")).toBe("等待审批");
    expect(displayIncidentStatus("WORKFLOW_FAILED")).toBe("自动流程执行失败");
    expect(displayWorkOrderStatus("WAITING_PARTS")).toBe("等待备件");
    expect(displayCreationMethod("RPA")).toBe("RPA 自动录入");
    expect(displayBoolean(true)).toBe("是");
    expect(displayBoolean(false)).toBe("否");
  });

  it("uses Chinese network and request error messages", () => {
    expect(formatErrorMessage(new TypeError("Failed to fetch"))).toBe("网络连接失败，请检查服务状态");
    expect(formatErrorMessage(new Error("Request failed"))).toBe("请求失败");
  });

  it("returns the next allowed work order action", () => {
    expect(nextWorkOrderAction("OPEN")).toBe("ASSIGNED");
    expect(nextWorkOrderAction("CLOSED")).toBeNull();
  });
});
