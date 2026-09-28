import { describe, expect, it } from "vitest";
import { envelopeFieldErrors, envelopeMessage } from "../client";
import { newIdempotencyKey } from "../useIngestion";

describe("error envelope helpers", () => {
  it("reads the standard envelope message", () => {
    const error = {
      response: {
        data: { error: { code: "validation_error", message: "Dữ liệu không hợp lệ.", request_id: "req_1" } },
      },
    };
    expect(envelopeMessage(error)).toBe("Dữ liệu không hợp lệ.");
  });

  it("falls back to the transport message and then to a generic text", () => {
    expect(envelopeMessage({ message: "Network Error" })).toBe("Network Error");
    expect(envelopeMessage({})).toBe("Đã có lỗi xảy ra");
  });

  it("exposes field errors from the envelope", () => {
    const error = {
      response: {
        data: {
          error: {
            code: "validation_error",
            message: "Dữ liệu không hợp lệ.",
            request_id: "req_1",
            field_errors: [{ field: "Idempotency-Key", message: "Bắt buộc có.", code: "missing" }],
          },
        },
      },
    };
    expect(envelopeFieldErrors(error)).toEqual([
      { field: "Idempotency-Key", message: "Bắt buộc có.", code: "missing" },
    ]);
    expect(envelopeFieldErrors(new Error("boom"))).toEqual([]);
  });
});

describe("idempotency keys", () => {
  it("generates a distinct non-empty key per upload attempt", () => {
    const first = newIdempotencyKey();
    const second = newIdempotencyKey();
    expect(first.length).toBeGreaterThan(0);
    expect(second).not.toBe(first);
  });
});
