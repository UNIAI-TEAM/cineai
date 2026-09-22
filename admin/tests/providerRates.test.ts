/** Hàm thuần bảng giá provider_rates: xem trước fen, đổi đơn vị, đổi thứ tự, dòng cho model chưa có giá. */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  emptyRateRow,
  moveRow,
  pendingUnpriced,
  rateFenPreview,
  rowForUnpriced,
  withUnit,
} from "../src/lib/providerRates.ts";

test("rateFenPreview matches backend rounding", () => {
  assert.equal(rateFenPreview(0.045, 7), 32);
  assert.equal(rateFenPreview(0.07, 7), 49);
  assert.equal(rateFenPreview(1, 7), 700);
  assert.equal(rateFenPreview(0, 7), 0);
  assert.equal(rateFenPreview(-1, 7), 0);
  assert.equal(rateFenPreview(0.0000001, 7), 1);
  assert.equal(rateFenPreview(1, 0), 0);
});

test("withUnit clears usd_out except for input/output unit", () => {
  const row = { pattern: "gpt-5.6-sol", unit: "per_m_input_output" as const, usd: 4, usd_out: 20, note: "" };
  assert.equal(withUnit(row, "per_m_tokens").usd_out, null);
  assert.equal(withUnit({ ...row, usd_out: null }, "per_m_input_output").usd_out, 0);
  assert.equal(withUnit(row, "per_m_input_output").usd_out, 20);
});

test("moveRow swaps neighbours and clamps", () => {
  assert.deepEqual(moveRow(["a", "b", "c"], 1, -1), ["b", "a", "c"]);
  assert.deepEqual(moveRow(["a", "b", "c"], 1, 1), ["a", "c", "b"]);
  assert.deepEqual(moveRow(["a", "b"], 0, -1), ["a", "b"]);
  assert.deepEqual(moveRow(["a", "b"], 1, 1), ["a", "b"]);
});

test("rowForUnpriced guesses unit by capability", () => {
  assert.equal(rowForUnpriced({ channel_id: "byteplus", model: "ep-1", capability: "image" }).unit, "per_image");
  assert.equal(rowForUnpriced({ channel_id: "byteplus", model: "ep-2", capability: "video" }).unit, "per_m_tokens");
  assert.equal(rowForUnpriced({ channel_id: "openai", model: "tts-x", capability: "audio" }).unit, "per_m_chars");
  const text = rowForUnpriced({ channel_id: "openai", model: "gpt-x", capability: "text" });
  assert.equal(text.unit, "per_m_input_output");
  assert.equal(text.usd_out, 0);
  assert.equal(text.pattern, "gpt-x");
  assert.equal(text.note, "openai");
});

test("pendingUnpriced hides models that already have an exact row", () => {
  const unpriced = [
    { channel_id: "b", model: "EP-1", capability: "image" },
    { channel_id: "b", model: "ep-2", capability: "image" },
  ];
  assert.deepEqual(
    pendingUnpriced(unpriced, [{ ...emptyRateRow(), pattern: "ep-1" }]).map((m) => m.model),
    ["ep-2"],
  );
});
