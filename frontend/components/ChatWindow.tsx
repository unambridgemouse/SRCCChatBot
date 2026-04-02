"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import MessageBubble from "./MessageBubble";
import RobotAvatar from "./RobotAvatar";

type Source = {
  doc_id: string;
  type: string;
  title: string;
  score: number;
  source?: string;
};

export type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  entities?: string[];
  isStreaming?: boolean;
  expandedQuery?: string;
  systemPrompt?: string;
};

type Props = {
  sessionId: string;
  initialMessages: Message[];
  onMessagesUpdate: (messages: Message[]) => void;
};

export default function ChatWindow({ sessionId, initialMessages, onMessagesUpdate }: Props) {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // セッション切り替え時にメッセージをリセット
  useEffect(() => {
    setMessages(initialMessages);
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(async () => {
    const query = input.trim();
    if (!query || isLoading) return;

    setInput("");
    setIsLoading(true);

    const userMsg: Message = { role: "user", content: query };
    const nextMessages: Message[] = [...messages, userMsg];
    setMessages(nextMessages);

    const withPlaceholder: Message[] = [
      ...nextMessages,
      { role: "assistant", content: "", isStreaming: true },
    ];
    setMessages(withPlaceholder);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query, session_id: sessionId }),
      });

      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulatedText = "";
      let sources: Source[] = [];
      let entities: string[] = [];
      let expandedQuery: string | undefined;
      let systemPrompt: string | undefined;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "text") {
              accumulatedText += data.text;
              setMessages((prev) =>
                prev.map((m, i) =>
                  i === prev.length - 1
                    ? { ...m, content: accumulatedText, isStreaming: true }
                    : m
                )
              );
            } else if (data.type === "done") {
              sources = data.sources ?? [];
              entities = data.extracted_entities ?? [];
              expandedQuery = data.expanded_query;
              systemPrompt = data.system_prompt;
            } else if (data.type === "error") {
              accumulatedText =
                "申し訳ありません、エラーが発生しました。しばらくしてから再試行してください。";
              setMessages((prev) =>
                prev.map((m, i) =>
                  i === prev.length - 1
                    ? { ...m, content: accumulatedText, isStreaming: false }
                    : m
                )
              );
            }
          } catch {
            // malformed JSON は無視
          }
        }
      }

      // ストリーム完了: isStreaming解除・メタデータ付与・localStorage保存
      setMessages((prev) => {
        const completed = prev.map((m, i) =>
          i === prev.length - 1
            ? { ...m, isStreaming: false, sources, entities, expandedQuery, systemPrompt }
            : m
        );
        onMessagesUpdate(completed);
        return completed;
      });
    } catch {
      setMessages((prev) => {
        const errored = prev.map((m, i) =>
          i === prev.length - 1
            ? {
                ...m,
                content: "エラーが発生しました。しばらくしてから再試行してください。",
                isStreaming: false,
              }
            : m
        );
        onMessagesUpdate(errored);
        return errored;
      });
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, messages, sessionId, onMessagesUpdate]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      {/* ロボットアバター + ステータス */}
      <div className="flex flex-col items-center py-4 border-b border-gray-100 bg-gray-950">
        <RobotAvatar isTalking={isLoading} size={140} />
        <p className="text-xs mt-2 h-4 transition-all duration-300"
           style={{ color: isLoading ? "#60a5fa" : "#6b7280" }}>
          {isLoading ? "回答中..." : messages.length === 0 ? "ご質問をどうぞ" : "待機中"}
        </p>
      </div>

      {/* メッセージエリア */}
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            <div className="text-center">
              <p className="text-lg mb-2">センちゃんについて何でも聞いてください</p>
              <p className="text-xs">例：「ロボットの強さは？」「ダメ詰めとは何ですか？」</p>
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* 入力エリア */}
      <div className="border-t border-gray-100 p-3 bg-gray-50">
        <div className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            className="flex-1 resize-none rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 bg-white min-h-[44px] max-h-32"
            placeholder="質問を入力してください... (Enter で送信、Shift+Enter で改行)"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded-xl px-4 py-3 text-sm font-medium transition-colors min-w-[64px]"
          >
            {isLoading ? "..." : "送信"}
          </button>
        </div>
      </div>
    </div>
  );
}
