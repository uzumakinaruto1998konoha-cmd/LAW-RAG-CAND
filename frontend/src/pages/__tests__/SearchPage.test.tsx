import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import SearchPage from "../SearchPage";
import { renderWithProviders } from "../../test/renderWithProviders";
import { post } from "../../shared/api/client";

vi.mock("../../shared/api/client", async (importOriginal) => {
  const actual = (await importOriginal()) as typeof import("../../shared/api/client");
  return { ...actual, get: vi.fn(), post: vi.fn() };
});

const postMock = vi.mocked(post);

const SEARCH_RESPONSE = {
  query: "thời hạn giải quyết",
  trace_id: "trace_abc123",
  query_type: "hybrid",
  as_of_date: null,
  result_count: 1,
  latency_ms: 42,
  results: [
    {
      rank: 1,
      chunk_id: "chunk_1",
      version_id: "ver_1",
      document_id: "doc_1",
      document_number: "31/2024/QH15",
      document_title: "Luật Đất đai",
      issuing_body: "Quốc hội",
      structural_path: "Chương III > Điều 12",
      heading: "Thời hạn giải quyết",
      snippet: "Nội dung trích đoạn kiểm thử.",
      page_start: 12,
      page_end: 13,
      score: 0.8123,
      validity_status: "in_force",
      is_verified: true,
    },
  ],
  warnings: ["Một số tài liệu trong kết quả chưa được duyệt."],
};

beforeEach(() => {
  postMock.mockReset();
});

describe("SearchPage", () => {
  it("submits the query and renders results, warnings and the trace link", async () => {
    postMock.mockResolvedValueOnce(SEARCH_RESPONSE);
    renderWithProviders(<SearchPage />);

    fireEvent.change(screen.getByLabelText("Câu hỏi hoặc từ khóa"), {
      target: { value: "thời hạn giải quyết" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Tìm kiếm" }));

    expect(await screen.findByText("Luật Đất đai")).toBeTruthy();
    expect(screen.getByText("Nội dung trích đoạn kiểm thử.")).toBeTruthy();
    expect(screen.getByText(/chưa được duyệt/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /trace_abc123/ })).toBeTruthy();
    expect(screen.getByText("Còn hiệu lực")).toBeTruthy();
    expect(postMock).toHaveBeenCalledWith(
      "/search",
      expect.objectContaining({ query: "thời hạn giải quyết", top_k: 10, query_type: "hybrid" })
    );
  });

  it("sends metadata filters only when the operator filled them in", async () => {
    postMock.mockResolvedValueOnce({ ...SEARCH_RESPONSE, results: [], result_count: 0 });
    renderWithProviders(<SearchPage />);

    fireEvent.change(screen.getByLabelText("Câu hỏi hoặc từ khóa"), {
      target: { value: "đất đai" },
    });
    fireEvent.change(screen.getByLabelText("document_type"), { target: { value: "Luật" } });
    fireEvent.click(screen.getByRole("button", { name: "Tìm kiếm" }));

    await screen.findByText(/Không có đoạn nào khớp/);
    expect(postMock).toHaveBeenCalledWith(
      "/search",
      expect.objectContaining({ filters: { document_type: "Luật" } })
    );
  });

  it("shows the standard envelope message when the API rejects the query", async () => {
    postMock.mockRejectedValueOnce({
      response: {
        data: {
          error: { code: "validation_error", message: "Câu truy vấn không hợp lệ.", request_id: "req_9" },
        },
      },
    });
    renderWithProviders(<SearchPage />);

    fireEvent.change(screen.getByLabelText("Câu hỏi hoặc từ khóa"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Tìm kiếm" }));

    expect(await screen.findByText("Câu truy vấn không hợp lệ.")).toBeTruthy();
  });

  it("does not call the API for an empty query", () => {
    renderWithProviders(<SearchPage />);

    fireEvent.click(screen.getByRole("button", { name: "Tìm kiếm" }));

    expect(postMock).not.toHaveBeenCalled();
    expect(screen.getByText("Vui lòng nhập câu hỏi.")).toBeTruthy();
  });
});
