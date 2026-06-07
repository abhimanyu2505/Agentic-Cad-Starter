import { useState } from "react";

function MessageList({ messages }) {
  return (
    <div className="chat-messages">
      {messages.length === 0 ? (
        <div className="empty-copy">Describe the part or assembly you want to build.</div>
      ) : null}
      {messages.map((message, index) => (
        <div
          key={`${message.role}-${index}`}
          className={`message message-${message.role === "assistant" ? "assistant" : message.role}`}
        >
          {message.content}
        </div>
      ))}
    </div>
  );
}

export default function ChatPanel({ messages, onSubmit, busy, error }) {
  const [prompt, setPrompt] = useState("");

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit(event);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (!prompt.trim() || busy) return;
    onSubmit(prompt.trim());
    setPrompt("");
  }

  return (
    <aside className="panel panel-left">
      <div className="panel-header">
        <div>
          <div className="eyebrow">Agentic CAD</div>
          <h1>Chat</h1>
        </div>
        <span className="pill">{messages.length} messages</span>
      </div>
      <MessageList messages={messages} />
      {error && <div className="message message-error">{error}</div>}
      <form className="chat-form" onSubmit={handleSubmit}>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Design a gear, add a shaft, or modify an assembly..."
          rows={3}
          disabled={busy}
        />
        <div className="form-footer">
          <span className="keyboard-hint">Press Enter to send, Shift+Enter for new line</span>
          <button type="submit" disabled={busy}>
            {busy ? "Working..." : "Send"}
          </button>
        </div>
      </form>
    </aside>
  );
}
