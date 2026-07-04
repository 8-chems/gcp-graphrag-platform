import { useState } from "react";
import { sendChatMessage, ChatResponse } from "../lib/api";
import { getIdToken } from "../lib/firebase";

interface Message {
  role: "user" | "assistant";
  content: string;
  meta?: ChatResponse;
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSend() {
    if (!input.trim() || loading) return;
    const question = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    try {
      const result = await sendChatMessage(question, sessionId, getIdToken);
      setSessionId(result.session_id);
      setMessages((prev) => [...prev, { role: "assistant", content: result.answer, meta: result }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong reaching the backend. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-panel">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <p>{m.content}</p>
            {m.meta && m.meta.used_agents.length > 0 && (
              <div className="meta">
                <span>agents: {m.meta.used_agents.join(", ")}</span>
              </div>
            )}
          </div>
        ))}
        {loading && <div className="message assistant">Thinking…</div>}
      </div>

      <div className="input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask a question about your documents…"
        />
        <button onClick={handleSend} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  );
}
