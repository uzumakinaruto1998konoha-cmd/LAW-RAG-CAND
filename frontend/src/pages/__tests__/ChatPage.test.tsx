import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import ChatPage from "../ChatPage";
import { renderWithProviders } from "../../test/renderWithProviders";
import { post } from "../../shared/api/client";
import { listStoredConversations } from "../../shared/conversations";

vi.mock("../../shared/api/client", async (importOriginal) => {
  const actual = (await importOriginal()) as typeof import("../../shared/api/client");
  return { ...actual, get: vi.fn(), post: vi.fn() };
});

const auth = vi.hoisted(() => ({ permissions: ["chat.query"] as string[] }));

vi.mock("../../features/auth/authContext", () => ({
  useAuth: () => ({
    user: {
      user_id: "u_user",
      username: "u_user",
      display_name: "Người dùng",
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

const postMock = vi.mocked(post);

const CHAT_RESPONSE = {
  message_id: "msg_1",
  conversation_id: "conv_9",
  answer: "Chưa đủ căn cứ trong kho tài liệu được phép truy cập để trả lời câu hỏi này.",
  insufficient_evidence: true,
  as_of_date: null,
  citations: [
    {
      citation_id: "cit_1",
      message_id: "msg_1",
      evidence_id: "ev_1",
      chunk_id: "chunk_1",
      version_id: "ver_1",
      document_number: "31/2024/QH15",
      document_title: "Luật Đất đai",
      issuing_body: "Quốc hội",
      structural_path: "Điều 12",
      excerpt: "Trích đoạn căn cứ.",
      page_start: 12,
      page_end: 12,
      viewer_url: "/viewer/ver_1?page=12",
      validity_status: "in_force",
      as_of_date: null,
      status: "valid",
    },
  ],
  evidence: [
    {
      evidence_id: "ev_1",
      chunk_id: "chunk_1",
      version_id: "ver_1",
      document_number: "31/2024/QH15",
      document_title: "Luật Đất đai",
      structural_path: "Điều 12",
      excerpt: "Trích đoạn căn cứ.",
      page_start: 12,
      page_end: 12,
      score: 0.7,
      is_verified: true,
      validity_status: "in_force",
    },
  ],
  warnings: ["Ngày áp dụng chưa được chọn."],
  trace_id: "trace_chat1",
};

beforeEach(() => {
  postMock.mockReset();
  window.localStorage.clear();
  auth.permissions = ["chat.query"];
});

describe("ChatPage", () => {
  it("shows the insufficient-evidence state, citations and warnings", async () => {
    postMock.mockResolvedValueOnce(CHAT_RESPONSE);
    renderWithProviders(<ChatPage />);

    fireEvent.change(screen.getByLabelText("Câu hỏi"), {
      target: { value: "Thời hạn giải quyết là bao lâu?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Gửi câu hỏi" }));

    expect(await screen.findByText("Không đủ căn cứ")).toBeTruthy();
    expect(screen.getByText(/không khẳng định vấn đề không được pháp luật quy định/)).toBeTruthy();
    expect(screen.getByText("Luật Đất đai")).toBeTruthy();
    expect(screen.getByText("Đã kiểm chứng")).toBeTruthy();
    expect(screen.getByText("Ngày áp dụng chưa được chọn.")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Mở trang nguồn/ }).getAttribute("href")).toContain(
      "/viewer/ver_1"
    );
    expect(postMock).toHaveBeenCalledWith(
      "/chat",
      expect.objectContaining({
        question: "Thời hạn giải quyết là bao lâu?",
        top_k: 5,
        query_type: "hybrid",
      })
    );
  });

  it("remembers the conversation for the local conversation index", async () => {
    postMock.mockResolvedValueOnce(CHAT_RESPONSE);
    renderWithProviders(<ChatPage />);

    fireEvent.change(screen.getByLabelText("Câu hỏi"), { target: { value: "Câu hỏi kiểm thử" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi câu hỏi" }));

    await screen.findByText("Không đủ căn cứ");
    const stored = listStoredConversations();
    expect(stored.map((item) => item.conversation_id)).toEqual(["conv_9"]);
    expect(stored[0].title).toBe("Câu hỏi kiểm thử");
  });

  it("renders the permission-denied state when chat.query is missing", () => {
    auth.permissions = [];
    renderWithProviders(<ChatPage />);

    expect(screen.getByText(/không có quyền hỏi đáp/)).toBeTruthy();
    expect(screen.queryByLabelText("Câu hỏi")).toBeNull();
  });
});
