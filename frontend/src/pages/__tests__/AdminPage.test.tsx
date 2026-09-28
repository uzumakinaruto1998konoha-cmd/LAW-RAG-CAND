import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import AdminPage from "../AdminPage";
import { renderWithProviders } from "../../test/renderWithProviders";
import { apiClient, get } from "../../shared/api/client";

vi.mock("../../shared/api/client", async (importOriginal) => {
  const actual = (await importOriginal()) as typeof import("../../shared/api/client");
  return { ...actual, get: vi.fn(), post: vi.fn(), apiClient: { get: vi.fn(), post: vi.fn() } };
});

const auth = vi.hoisted(() => ({ permissions: ["document.upload", "document.view"] as string[] }));

vi.mock("../../features/auth/authContext", () => ({
  useAuth: () => ({
    user: {
      user_id: "u_admin",
      username: "u_admin",
      display_name: "Quản trị tri thức",
      is_system: false,
      permissions: auth.permissions,
    },
    token: "token-test",
    login: vi.fn(),
    logout: vi.fn(),
    loading: false,
    hasPermission: (permission: string) => auth.permissions.includes(permission),
  }),
}));

const getMock = vi.mocked(get);
const postMock = vi.mocked(apiClient.post);

const DOCUMENTS = {
  count: 1,
  documents: [
    {
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
      is_verified: false,
      collection_ids: ["col_public"],
      chunk_count: 120,
    },
  ],
};

const UPLOAD_RECEIPT = {
  job_id: "job_1",
  status: "uploaded",
  document_id: null,
  version_id: null,
  duplicate_match: true,
  original_filename: "van-ban.pdf",
  media_type: "application/pdf",
  size_bytes: 2048,
  sha256: "a".repeat(64),
  trace_id: "trace_upload_1",
  warnings: ["Bản tải lên trùng nội dung đã có; job hiện tại trỏ tới job gốc."],
};

beforeEach(() => {
  getMock.mockReset();
  postMock.mockReset();
  auth.permissions = ["document.upload", "document.view"];
});

describe("AdminPage", () => {
  it("summarises the readable knowledge base and hides missing admin APIs behind an explicit note", async () => {
    getMock.mockImplementation((url: string) => {
      if (url === "/documents") return Promise.resolve(DOCUMENTS);
      return Promise.reject(new Error(`unexpected url ${url}`));
    });

    renderWithProviders(<AdminPage />);

    expect(await screen.findByText(/1 phiên bản tài liệu bạn được đọc/)).toBeTruthy();
    expect(screen.getByText("Chưa khả dụng trong /api/v1")).toBeTruthy();
    expect(screen.getByText("Duyệt và release phiên bản")).toBeTruthy();
    expect(screen.getByText("document.upload")).toBeTruthy();
  });

  it("uploads a raw body with filename and idempotency metadata, then reports the duplicate job", async () => {
    getMock.mockImplementation((url: string) => {
      if (url === "/documents") return Promise.resolve(DOCUMENTS);
      if (url === "/jobs/job_1") {
        return Promise.resolve({
          job_id: "job_1",
          status: "review_required",
          attempt: 1,
          error_code: null,
          original_filename: "van-ban.pdf",
          media_type: "application/pdf",
          size_bytes: 2048,
          sha256: "a".repeat(64),
          uploader_id: "u_admin",
          trace_id: "trace_upload_1",
          created_at: "2026-09-27T10:00:00Z",
          updated_at: "2026-09-27T10:05:00Z",
        });
      }
      return Promise.reject(new Error(`unexpected url ${url}`));
    });
    postMock.mockResolvedValueOnce({ data: UPLOAD_RECEIPT });

    renderWithProviders(<AdminPage />);

    const file = new File(["%PDF-1.7"], "van-ban.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Tệp"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Tải lên" }));

    expect(await screen.findByText("Job job_1")).toBeTruthy();
    expect(screen.getByText("trùng nội dung")).toBeTruthy();
    expect(await screen.findByText("Cần người duyệt")).toBeTruthy();

    const [url, body, config] = postMock.mock.calls[0];
    expect(url).toBe("/documents/upload");
    expect(body).toBe(file);
    expect(config?.params).toEqual({ filename: "van-ban.pdf" });
    expect(config?.headers?.["Idempotency-Key"]).toBeTruthy();
    expect(config?.headers?.["Content-Type"]).toBe("application/pdf");
  });

  it("shows the permission-denied state for an account without admin permissions", () => {
    auth.permissions = [];
    renderWithProviders(<AdminPage />);

    expect(screen.getByText(/không có quyền quản trị/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Tải lên" })).toBeNull();
  });
});
