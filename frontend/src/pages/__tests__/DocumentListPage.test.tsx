import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import DocumentListPage from "../DocumentListPage";
import { renderWithProviders } from "../../test/renderWithProviders";
import { get } from "../../shared/api/client";

vi.mock("../../shared/api/client", async (importOriginal) => {
  const actual = (await importOriginal()) as typeof import("../../shared/api/client");
  return { ...actual, get: vi.fn(), post: vi.fn() };
});

const getMock = vi.mocked(get);

function summary(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    document_id: "doc_1",
    version_id: "ver_1",
    document_number: "31/2024/QH15",
    title: "Luật Đất đai",
    issuing_body: "Quốc hội",
    document_type: "Luật",
    issue_date: "2024-01-18",
    effective_date: "2025-01-01",
    expiry_date: null,
    validity_status: "in_force",
    is_verified: true,
    collection_ids: ["col_public"],
    chunk_count: 120,
    ...overrides,
  };
}

const DOCUMENTS = {
  count: 2,
  documents: [
    summary(),
    summary({
      document_id: "doc_2",
      version_id: "ver_2",
      document_number: "10/2023/ND-CP",
      title: "Nghị định về đất đai",
      issuing_body: "Chính phủ",
      document_type: "Nghị định",
      validity_status: "expired",
      is_verified: false,
      collection_ids: [],
      chunk_count: 8,
    }),
  ],
};

beforeEach(() => {
  getMock.mockReset();
});

describe("DocumentListPage", () => {
  it("lists readable documents with validity and verification state", async () => {
    getMock.mockResolvedValueOnce(DOCUMENTS);
    renderWithProviders(<DocumentListPage />);

    expect(await screen.findByText("Luật Đất đai")).toBeTruthy();
    expect(screen.getByText("Nghị định về đất đai")).toBeTruthy();
    expect(screen.getByText("Còn hiệu lực")).toBeTruthy();
    expect(screen.getByText("Hết hiệu lực")).toBeTruthy();
    expect(screen.getByText("Chưa duyệt")).toBeTruthy();
    expect(screen.getByText(/2\/2 tài liệu/)).toBeTruthy();
  });

  it("filters client-side by text and hides non-matching documents", async () => {
    getMock.mockResolvedValueOnce(DOCUMENTS);
    renderWithProviders(<DocumentListPage />);

    await screen.findByText("Luật Đất đai");
    fireEvent.change(screen.getByLabelText("Tìm theo số hiệu, tiêu đề, cơ quan"), {
      target: { value: "nghị định" },
    });

    expect(screen.queryByText("Luật Đất đai")).toBeNull();
    expect(screen.getByText("Nghị định về đất đai")).toBeTruthy();
    expect(screen.getByText(/1\/2 tài liệu/)).toBeTruthy();
  });

  it("describes an empty result set without claiming the law is silent", async () => {
    getMock.mockResolvedValueOnce({ count: 0, documents: [] });
    renderWithProviders(<DocumentListPage />);

    expect(await screen.findByText(/Chưa có tài liệu nào được release/)).toBeTruthy();
  });

  it("renders the envelope message when the documents endpoint fails", async () => {
    getMock.mockRejectedValueOnce({
      response: {
        data: { error: { code: "forbidden", message: "Không đủ quyền.", request_id: "req_2" } },
      },
    });
    renderWithProviders(<DocumentListPage />);

    expect(await screen.findByText("Không đủ quyền.")).toBeTruthy();
  });
});
