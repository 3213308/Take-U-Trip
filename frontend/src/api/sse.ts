/**
 * 通用 SSE 流解析器 — POST 请求无法用 EventSource，基于 fetch + ReadableStream 手写。
 * 处理：\r\n 归一化、按 \n\n 切块、event:/data: 行、多 data 行拼接、
 * 心跳注释（: 开头）忽略、结尾残留 flush、坏 JSON 跳过不中断。
 */
export async function consumeSSE(
  resp: Response,
  onEvent: (type: string, data: unknown) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!resp.ok) {
    let detail = "";
    try {
      detail = await resp.text();
    } catch {
      /* 读不到响应体就算了 */
    }
    throw new Error(`请求失败（HTTP ${resp.status}）${detail ? `：${detail}` : ""}`);
  }
  if (!resp.body) throw new Error("响应没有可读取的数据流");

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventType = "";

  const dispatchBlock = (block: string) => {
    const lines = block.replace(/\r\n/g, "\n").split("\n");
    const dataLines: string[] = [];
    for (const line of lines) {
      if (!line || line.startsWith(":")) continue; // 心跳/注释
      if (line.startsWith("event:")) eventType = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    try {
      onEvent(eventType || "message", JSON.parse(dataLines.join("\n")));
    } catch (e) {
      console.warn("[sse] 跳过无法解析的事件", e);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        dispatchBlock(buffer.slice(0, idx));
        buffer = buffer.slice(idx + 2);
      }
    }
    buffer += decoder.decode(); // flush 残留
    if (buffer.trim()) dispatchBlock(buffer);
  } catch (e) {
    if (signal?.aborted) return; // 用户主动停止，静默退出
    throw e;
  }
}
