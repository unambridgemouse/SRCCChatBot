"use client";

import { useState, useEffect, useCallback } from "react";
import ChatWindow, { Message } from "@/components/ChatWindow";
import Sidebar, { ChatSession } from "@/components/Sidebar";

const STORAGE_KEY = "srcc_chat_sessions";

function generateId(): string {
  return crypto.randomUUID();
}

function newSession(): ChatSession {
  return {
    id: generateId(),
    title: "新しいチャット",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messages: [],
  };
}

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [mounted, setMounted] = useState(false);

  // localStorageから復元
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed: ChatSession[] = JSON.parse(stored);
        if (parsed.length > 0) {
          setSessions(parsed);
          setActiveId(parsed[0].id);
          setMounted(true);
          return;
        }
      }
    } catch {
      // 破損データは無視
    }
    // 履歴なし → 新規セッションを作成
    const s = newSession();
    setSessions([s]);
    setActiveId(s.id);
    setMounted(true);
  }, []);

  function saveSessions(updated: ChatSession[]) {
    setSessions(updated);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    } catch {
      // localStorage容量超過等は無視
    }
  }

  const handleNewChat = useCallback(() => {
    const s = newSession();
    saveSessions([s, ...sessions]);
    setActiveId(s.id);
  }, [sessions]);

  const handleSelect = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const handleDelete = useCallback(
    (id: string) => {
      const updated = sessions.filter((s) => s.id !== id);
      if (updated.length === 0) {
        const s = newSession();
        saveSessions([s]);
        setActiveId(s.id);
      } else {
        saveSessions(updated);
        if (activeId === id) setActiveId(updated[0].id);
      }
    },
    [sessions, activeId]
  );

  const handleClearAll = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    const s = newSession();
    setSessions([s]);
    setActiveId(s.id);
  }, []);

  const handleMessagesUpdate = useCallback(
    (messages: Message[]) => {
      const firstUserMsg = messages.find((m) => m.role === "user");
      const title = firstUserMsg
        ? firstUserMsg.content.slice(0, 40) + (firstUserMsg.content.length > 40 ? "…" : "")
        : "新しいチャット";
      const updated = sessions.map((s) =>
        s.id === activeId
          ? { ...s, messages, title, updatedAt: new Date().toISOString() }
          : s
      );
      saveSessions(updated);
    },
    [sessions, activeId]
  );

  const activeSession = sessions.find((s) => s.id === activeId);

  if (!mounted) return null;

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={handleSelect}
        onNewChat={handleNewChat}
        onDelete={handleDelete}
        onClearAll={handleClearAll}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="px-6 py-3 border-b border-gray-200 bg-white flex-shrink-0">
          <h1 className="text-lg font-bold text-gray-800">SRCC FAQ Bot</h1>
          <p className="text-xs text-gray-500">
            センスロボットコールセンターサポートシステム
          </p>
        </header>
        <div className="flex-1 overflow-hidden p-4">
          {activeSession && (
            <ChatWindow
              key={activeId}
              sessionId={activeId}
              initialMessages={activeSession.messages}
              onMessagesUpdate={handleMessagesUpdate}
            />
          )}
        </div>
      </div>
    </div>
  );
}
