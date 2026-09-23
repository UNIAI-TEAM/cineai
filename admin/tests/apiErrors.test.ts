/** Mã lỗi backend → câu tiếng Việt: điền tham số, định dạng tiền *_fen, mã lạ trả rỗng. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { ADMIN_ERROR_MESSAGES, translateErrorCode } from "../src/lib/apiErrors.ts";

const fmt = (fen: number) => `${fen}f`;

test("translates registered code with params", () => {
  assert.equal(translateErrorCode("billing.order_closed", undefined, fmt), ADMIN_ERROR_MESSAGES["billing.order_closed"]);
  assert.equal(translateErrorCode("task.mock_limit", { max: 3 }, fmt), "Chỉ chạy tối đa 3 lượt thử cùng lúc");
});

test("formats *_fen params and strips suffix", () => {
  const text = translateErrorCode("billing.insufficient_balance", { need_fen: 500, available_fen: 20 }, fmt);
  assert.match(text, /500f/);
  assert.match(text, /20f/);
  assert.doesNotMatch(text, /\{/);
});

test("unknown or missing code returns empty string", () => {
  assert.equal(translateErrorCode("nope.unknown", {}, fmt), "");
  assert.equal(translateErrorCode(undefined, {}, fmt), "");
});

test("no Chinese left in admin error table", () => {
  for (const text of Object.values(ADMIN_ERROR_MESSAGES)) assert.doesNotMatch(text, /[一-鿿]/);
});
