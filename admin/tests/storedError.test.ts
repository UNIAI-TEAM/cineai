/** Lỗi đã lưu → câu tiếng Việt + lỗi gốc; không có mã thì giữ nguyên văn. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { ADMIN_ERROR_MESSAGES } from "../src/lib/apiErrors.ts";
import { describeStoredError } from "../src/lib/storedError.ts";

const fmt = (fen: number) => `${fen}f`;

test("registered code: translated text, raw kept in detail", () => {
  const view = describeStoredError("任务已取消", "project.cancelled", null, fmt);
  assert.deepEqual(view, {
    text: ADMIN_ERROR_MESSAGES["project.cancelled"],
    detail: "project.cancelled · 任务已取消",
    translated: true,
  });
});

test("params and *_fen are interpolated", () => {
  const view = describeStoredError("x", "drama.episode_gen_incomplete", { done: 2, total: 5 }, fmt);
  assert.equal(view?.text, "Mới viết xong 2/5 tập, vui lòng thử lại");
  const money = describeStoredError("", "billing.insufficient_balance", { need_fen: 500, available_fen: 20 }, fmt);
  assert.match(money?.text ?? "", /500f.*20f/);
  assert.equal(money?.detail, "billing.insufficient_balance");
});

test("no code: raw message as is, no detail", () => {
  assert.deepEqual(describeStoredError("  upstream 500  ", null, null, fmt), {
    text: "upstream 500",
    detail: "",
    translated: false,
  });
});

test("unknown code: raw message shown, code kept in detail", () => {
  assert.deepEqual(describeStoredError("boom", "executor_crash", undefined, fmt), {
    text: "boom",
    detail: "executor_crash",
    translated: false,
  });
  assert.deepEqual(describeStoredError("", "executor_crash", undefined, fmt), {
    text: "executor_crash",
    detail: "",
    translated: false,
  });
});

test("nothing stored returns null", () => {
  assert.equal(describeStoredError(null, null, null, fmt), null);
  assert.equal(describeStoredError("   ", "", {}, fmt), null);
});
