export type SseFrame = { event: string; data: string };

/**
 * A minimal server-sent-events parser. Feed it raw chunks of text as they
 * arrive from a stream via `push`; it returns any complete frames found so
 * far. Call `flush` at the end of the stream to emit a final frame that
 * never got a trailing blank line.
 */
export function createSseParser(): {
  push(chunk: string): SseFrame[];
  flush(): SseFrame[];
} {
  let buffer = "";
  let eventName: string | null = null;
  let dataLines: string[] = [];
  let sawField = false;

  function resetFrame() {
    eventName = null;
    dataLines = [];
    sawField = false;
  }

  function emit(frames: SseFrame[]) {
    if (!sawField) return;
    frames.push({ event: eventName ?? "message", data: dataLines.join("\n") });
    resetFrame();
  }

  function consumeLine(line: string, frames: SseFrame[]) {
    if (line === "") {
      emit(frames);
      return;
    }
    if (line.startsWith(":")) {
      return;
    }
    const colonIndex = line.indexOf(":");
    let field: string;
    let value: string;
    if (colonIndex === -1) {
      field = line;
      value = "";
    } else {
      field = line.slice(0, colonIndex);
      value = line.slice(colonIndex + 1);
      if (value.startsWith(" ")) value = value.slice(1);
    }

    if (field === "event") {
      eventName = value;
      sawField = true;
    } else if (field === "data") {
      dataLines.push(value);
      sawField = true;
    }
    // unknown fields are ignored
  }

  function push(chunk: string): SseFrame[] {
    buffer += chunk;
    const frames: SseFrame[] = [];
    let start = 0;
    while (true) {
      const newlineIndex = buffer.indexOf("\n", start);
      if (newlineIndex === -1) break;
      let line = buffer.slice(start, newlineIndex);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      consumeLine(line, frames);
      start = newlineIndex + 1;
    }
    buffer = buffer.slice(start);
    return frames;
  }

  function flush(): SseFrame[] {
    const frames: SseFrame[] = [];
    if (buffer.length > 0) {
      let line = buffer;
      if (line.endsWith("\r")) line = line.slice(0, -1);
      consumeLine(line, frames);
      buffer = "";
    }
    emit(frames);
    return frames;
  }

  return { push, flush };
}
