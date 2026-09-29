import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import ConversationsPage from "../ConversationsPage";
import { renderWithProviders } from "../../test/renderWithProviders";
import { get } from "../../shared/api/client";

vi.mock("../../shared/api/client", async (importOriginal) => {
  const actual = (await importOriginal()) as typeof import("../../shared/api/client");
  return { ...actual, get: vi.fn(), post: vi.fn() };
});

const getMock = vi.mocked(get);

describe("ConversationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state when user has no conversations", async () => {
    getMock.mockResolvedValueOnce({
      count: 0,
      limit: 50,
      offset: 0,
      conversations: [],
    });

    renderWithProviders(<ConversationsPage />);

    expect(
      await screen.findByText(/Bạn chưa có phiên hội thoại nào trên hệ thống/i),
    ).toBeTruthy();
  });

  it("renders conversation list returned by server", async () => {
    getMock.mockResolvedValueOnce({
      count: 1,
      limit: 50,
      offset: 0,
      conversations: [
        {
          conversation_id: "conv_test_1",
          user_id: "u_user",
          title: "Tìm hiểu Luật Đất đai",
          created_at: "2026-09-29T10:00:00Z",
          updated_at: "2026-09-29T10:30:00Z",
          is_archived: false,
        },
      ],
    });

    renderWithProviders(<ConversationsPage />);

    expect(await screen.findByText("Tìm hiểu Luật Đất đai")).toBeTruthy();
    expect(screen.getByText("conv_test_1")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Mở hội thoại" })).toBeTruthy();
  });
});
