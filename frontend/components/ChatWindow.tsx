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

// タイプライター描画のチューニング
// SSEトークンは不規則な塊で届くため、受信と描画を分離して一定速度で吐き出す。
const TYPE_TICK_MS = 16; // 描画間隔（約60fps）
const TYPE_BASE_CPS = 95; // 基本の表示速度（文字/秒）。トークン到着速度に近づけるほど速いが、超えても意味はない
const TYPE_CATCHUP_GAIN = 4.0; // 未表示分に応じた加速（遅れを吸収し、全体の完了時間を伸ばさない）
const TYPE_MAX_DT = 0.25; // 1tickで進める最大秒数（タブ復帰時の一気出しを防ぐ）

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

    // 受信（target）と描画（shown）を分離し、一定速度で滑らかに吐き出す
    let target = ""; // 受信済みの全文
    let shown = 0; // 表示済み文字数（小数で保持し、tickごとに進める）
    let streamEnded = false;
    let typeTimer: ReturnType<typeof setInterval> | null = null;
    const stopTypewriter = () => {
      if (typeTimer) clearInterval(typeTimer);
      typeTimer = null;
    };

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
      let sources: Source[] = [];
      let entities: string[] = [];
      let expandedQuery: string | undefined;
      let systemPrompt: string | undefined;

      const updateLast = (content: string, isStreaming: boolean) =>
        setMessages((prev) =>
          prev.map((m, i) => (i === prev.length - 1 ? { ...m, content, isStreaming } : m))
        );

      // 一定速度で1文字ずつ描画。未表示分が溜まるほど緩やかに加速して受信に追いつく。
      let lastTs = performance.now();
      const drained = new Promise<void>((resolve) => {
        typeTimer = setInterval(() => {
          const now = performance.now();
          const dt = Math.min((now - lastTs) / 1000, TYPE_MAX_DT);
          lastTs = now;

          const backlog = target.length - shown;
          if (backlog > 0) {
            const speed = TYPE_BASE_CPS + backlog * TYPE_CATCHUP_GAIN;
            shown = Math.min(target.length, shown + speed * dt);
            updateLast(target.slice(0, Math.floor(shown)), true);
          }

          if (streamEnded && shown >= target.length) {
            stopTypewriter();
            resolve();
          }
        }, TYPE_TICK_MS);
      });

      try {
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
                target += data.text; // 描画はtimerに任せ、ここでは溜めるだけ
              } else if (data.type === "done") {
                sources = data.sources ?? [];
                entities = data.extracted_entities ?? [];
                expandedQuery = data.expanded_query;
                systemPrompt = data.system_prompt;
              } else if (data.type === "error") {
                target =
                  "申し訳ありません、エラーが発生しました。しばらくしてから再試行してください。";
              }
            } catch {
              // malformed JSON は無視
            }
          }
        }
      } finally {
        streamEnded = true; // 受信終了。残りを描き切ったらdrainedが解決する
      }

      await drained; // 描画が受信に追いつくのを待ってから確定させる

      // ストリーム完了: isStreaming解除・メタデータ付与・localStorage保存
      setMessages((prev) => {
        const completed = prev.map((m, i) =>
          i === prev.length - 1
            ? { ...m, content: target, isStreaming: false, sources, entities, expandedQuery, systemPrompt }
            : m
        );
        onMessagesUpdate(completed);
        return completed;
      });
    } catch {
      stopTypewriter();
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
      stopTypewriter();
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
      <div className="flex flex-col items-center py-4 border-b border-gray-100"
        style={{
          backgroundColor: "#C8923A",
          backgroundImage: [
            "repeating-linear-gradient(0deg,   rgba(92,48,16,0.55) 0px, rgba(92,48,16,0.55) 1px, transparent 1px, transparent 18px)",
            "repeating-linear-gradient(90deg,  rgba(92,48,16,0.55) 0px, rgba(92,48,16,0.55) 1px, transparent 1px, transparent 18px)",
          ].join(","),
        }}>
        <RobotAvatar isTalking={isLoading} size={140} />
        <p className="text-xs mt-2 h-4 transition-all duration-300 font-bold"
           style={{
             color: isLoading ? "#bfefff" : "#ffffff",
             textShadow: "0 1px 3px rgba(0,0,0,0.7)",
           }}>
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
