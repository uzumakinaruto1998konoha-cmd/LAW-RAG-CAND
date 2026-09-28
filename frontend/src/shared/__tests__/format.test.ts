import { describe, expect, it } from "vitest";
import {
  citationStatusLabel,
  formatBytes,
  formatDate,
  formatScore,
  isTerminalJobStatus,
  jobStatusLabel,
  pageRange,
  titleFromQuestion,
  truncate,
} from "../format";

describe("format helpers", () => {
  it("formats ISO dates for Vietnamese display", () => {
    expect(formatDate("2026-09-27")).toBe("27/09/2026");
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
  });

  it("keeps unknown date strings untouched instead of inventing a value", () => {
    expect(formatDate("không rõ")).toBe("không rõ");
  });

  it("renders page ranges and single pages", () => {
    expect(pageRange(1, 3)).toBe("trang 1–3");
    expect(pageRange(4, 4)).toBe("trang 4");
    expect(pageRange(null, 2)).toBe("trang 2");
    expect(pageRange(null, null)).toBe("—");
  });

  it("formats scores with three decimals", () => {
    expect(formatScore(0.45678)).toBe("0.457");
    expect(formatScore(null)).toBe("—");
  });

  it("formats byte sizes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.00 MB");
  });

  it("maps known server status codes and falls back to the raw code", () => {
    expect(jobStatusLabel("review_required")).toBe("Cần người duyệt");
    expect(jobStatusLabel("brand_new_code")).toBe("brand_new_code");
    expect(citationStatusLabel("valid")).toBe("Đã kiểm chứng");
    expect(citationStatusLabel(undefined)).toBe("—");
  });

  it("knows which job states stop polling", () => {
    expect(isTerminalJobStatus("indexed")).toBe(true);
    expect(isTerminalJobStatus("extracting")).toBe(false);
    expect(isTerminalJobStatus(null)).toBe(false);
  });

  it("normalises whitespace when deriving a conversation title", () => {
    expect(titleFromQuestion("  Thời   hạn  giải quyết?  ")).toBe("Thời hạn giải quyết?");
    expect(truncate("a".repeat(10), 4)).toBe("aaaa…");
  });
});
