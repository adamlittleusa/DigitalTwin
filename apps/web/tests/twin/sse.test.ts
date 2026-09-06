import { describe, expect, it } from "vitest";
import { createSseParser } from "@/twin/sse";

describe("createSseParser", () => {
  it("parses a simple event/data frame", () => {
    const parser = createSseParser();
    const frames = parser.push("event: step\ndata: {\"phase\":\"thinking\"}\n\n");
    expect(frames).toEqual([{ event: "step", data: '{"phase":"thinking"}' }]);
  });

  it("emits message as the event name when none is given", () => {
    const parser = createSseParser();
    const frames = parser.push("data: hello\n\n");
    expect(frames).toEqual([{ event: "message", data: "hello" }]);
  });

  it("joins multiple data lines with a newline", () => {
    const parser = createSseParser();
    const frames = parser.push("event: delta\ndata: line one\ndata: line two\n\n");
    expect(frames).toEqual([{ event: "delta", data: "line one\nline two" }]);
  });

  it("ignores comment lines starting with a colon", () => {
    const parser = createSseParser();
    const frames = parser.push(":keepalive\nevent: ping\ndata: 1\n\n");
    expect(frames).toEqual([{ event: "ping", data: "1" }]);
  });

  it("ignores unknown fields", () => {
    const parser = createSseParser();
    const frames = parser.push("id: 5\nretry: 1000\nevent: step\ndata: x\n\n");
    expect(frames).toEqual([{ event: "step", data: "x" }]);
  });

  it("accepts a missing space after the colon", () => {
    const parser = createSseParser();
    const frames = parser.push("event:step\ndata:x\n\n");
    expect(frames).toEqual([{ event: "step", data: "x" }]);
  });

  it("accepts CRLF line endings", () => {
    const parser = createSseParser();
    const frames = parser.push("event: step\r\ndata: x\r\n\r\n");
    expect(frames).toEqual([{ event: "step", data: "x" }]);
  });

  it("splits a frame mid-line across pushes", () => {
    const parser = createSseParser();
    const first = parser.push("event: st");
    expect(first).toEqual([]);
    const second = parser.push("ep\ndata: x\n\n");
    expect(second).toEqual([{ event: "step", data: "x" }]);
  });

  it("splits a frame mid-frame across pushes (holds partial line at blank boundary)", () => {
    const parser = createSseParser();
    const first = parser.push("event: step\ndata: x\n");
    expect(first).toEqual([]);
    const second = parser.push("\nevent: delta\ndata: y\n\n");
    expect(second).toEqual([
      { event: "step", data: "x" },
      { event: "delta", data: "y" },
    ]);
  });

  it("parses multiple frames in one push", () => {
    const parser = createSseParser();
    const frames = parser.push("event: a\ndata: 1\n\nevent: b\ndata: 2\n\n");
    expect(frames).toEqual([
      { event: "a", data: "1" },
      { event: "b", data: "2" },
    ]);
  });

  it("flush emits a pending frame without a trailing blank line", () => {
    const parser = createSseParser();
    const pushed = parser.push("event: done\ndata: x");
    expect(pushed).toEqual([]);
    const flushed = parser.flush();
    expect(flushed).toEqual([{ event: "done", data: "x" }]);
  });

  it("flush on an empty buffer returns no frames", () => {
    const parser = createSseParser();
    parser.push("event: a\ndata: 1\n\n");
    expect(parser.flush()).toEqual([]);
  });
});
