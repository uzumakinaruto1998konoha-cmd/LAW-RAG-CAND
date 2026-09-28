import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import TracePage from "../TracePage";
import { renderWithProviders } from "../../test/renderWithProviders";
import { get } from "../../shared/api/client";

vi.mock("../../shared/api/client", async (importOriginal) => {
  const actual = (await importOriginal()) as typeof import("../../shared/api/client");
  return { ...actual, get: vi.fn(), post: vi.fn() };
});

const getMock = vi.mocked(get);

beforeEach(() => {
  getMock.mockReset();
});

describe("TracePage", () => {
  it("renders the audit metadata and ranked chunk identifiers", async () => {
    getMock.mockResolvedValueOnce({
      trace_id: "trace_abc123",
      user_id: "u_user",
      query: "thời hạn giải quyết",
      query_type: "hybrid",
      as_of_date: "2026-09-27",
      filters: { document_type: "Luật" },
      manifest_id: "manifest_4",
      result_count: 1,
      latency_ms: 37,
      created_at: "2026-09-27T10:00:00Z",
      results: [{ rank: 1, chunk_id: "chunk_1", score: 0.8123, retrieval_method: "lexical" }],
    });

    renderWithProviders(<TracePage />, { route: "/traces/trace_abc123", path: "/traces/:traceId" });

    expect(await screen.findByText("chunk_1")).toBeTruthy();
    expect(screen.getByText("thời hạn giải quyết")).toBeTruthy();
    expect(screen.getByText("manifest_4")).toBeTruthy();
    expect(screen.getByText("37 ms")).toBeTruthy();
    expect(screen.getByText("document_type=Luật")).toBeTruthy();
    expect(getMock).toHaveBeenCalledWith("/traces/trace_abc123");
  });

  it("explains that a trace is only visible to its owner or the audit role", async () => {
    getMock.mockRejectedValueOnce({
      response: {
        data: { error: { code: "not_found", message: "Không tìm thấy trace.", request_id: "req_3" } },
      },
    });

    renderWithProviders(<TracePage />, { route: "/traces/trace_missing", path: "/traces/:traceId" });

    expect(await screen.findByText(/Không tìm thấy trace./)).toBeTruthy();
    expect(screen.getByText(/audit.view/)).toBeTruthy();
  });
});
