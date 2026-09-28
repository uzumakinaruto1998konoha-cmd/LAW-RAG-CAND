import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import HealthPage from "../HealthPage";
import { renderWithProviders } from "../../test/renderWithProviders";
import { get } from "../../shared/api/client";

vi.mock("../../shared/api/client", async (importOriginal) => {
  const actual = (await importOriginal()) as typeof import("../../shared/api/client");
  return { ...actual, get: vi.fn(), post: vi.fn() };
});

const getMock = vi.mocked(get);

const HEALTH = {
  status: "ok",
  phase: "PHASE 5 - Web Application / API",
  architecture_version: "1.1-retrieval-rag-api",
};

const READY_OK = {
  status: "ready",
  checks: [{ name: "retrieval", status: "ok", detail: null }],
  indexed_chunk_count: 1200,
  indexed_version_count: 30,
};

function mockEndpoints(readiness: unknown) {
  getMock.mockImplementation((url: string) => {
    if (url === "/health") return Promise.resolve(HEALTH);
    if (url === "/ready") return Promise.resolve(readiness);
    return Promise.reject(new Error(`unexpected url ${url}`));
  });
}

beforeEach(() => {
  getMock.mockReset();
});

describe("HealthPage", () => {
  it("reports liveness and readiness with index sizes", async () => {
    mockEndpoints(READY_OK);
    renderWithProviders(<HealthPage />);

    expect(await screen.findByText("1.1-retrieval-rag-api")).toBeTruthy();
    expect(screen.getByText("PHASE 5 - Web Application / API")).toBeTruthy();
    expect(screen.getByText("1200")).toBeTruthy();
    expect(screen.getByText("30")).toBeTruthy();
    expect(screen.getByText("retrieval")).toBeTruthy();
    expect(screen.queryByText(/đang ở trạng thái suy giảm/)).toBeNull();
  });

  it("presents a degraded subsystem as a warning instead of a healthy state", async () => {
    mockEndpoints({
      status: "degraded",
      checks: [
        { name: "retrieval", status: "degraded", detail: "index chưa được build" },
        { name: "ingestion", status: "ok", detail: null },
      ],
      indexed_chunk_count: 0,
      indexed_version_count: 0,
    });
    renderWithProviders(<HealthPage />);

    expect(await screen.findByText("Hệ thống đang ở trạng thái suy giảm")).toBeTruthy();
    expect(screen.getByText("index chưa được build")).toBeTruthy();
    expect(screen.getByText(/stale index/)).toBeTruthy();
  });

  it("explains that the API may be down when liveness fails", async () => {
    getMock.mockRejectedValue({
      response: { data: { error: { code: "network", message: "Không kết nối được API.", request_id: "req_1" } } },
    });
    renderWithProviders(<HealthPage />);

    // Liveness and readiness both fail against a down API, so the message repeats.
    expect(await screen.findAllByText(/Không kết nối được API/)).toHaveLength(2);
  });
});
