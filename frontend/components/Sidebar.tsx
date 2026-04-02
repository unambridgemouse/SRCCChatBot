"use client";

type Message = {
  role: "user" | "assistant";
  content: string;
};

export type ChatSession = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: Message[];
};

type Props = {
  sessions: ChatSession[];
  activeId: string;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  onClearAll: () => void;
};

function formatDateLabel(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffDays === 0) return "今日";
  if (diffDays === 1) return "昨日";
  if (diffDays < 7) return "過去7日間";
  return d.toLocaleDateString("ja-JP", { month: "long", day: "numeric" });
}

export default function Sidebar({ sessions, activeId, onSelect, onNewChat, onDelete, onClearAll }: Props) {
  // グループ化（日付ラベル順）
  const grouped: { label: string; items: ChatSession[] }[] = [];
  for (const s of sessions) {
    const label = formatDateLabel(s.updatedAt);
    const g = grouped.find((g) => g.label === label);
    if (g) g.items.push(s);
    else grouped.push({ label, items: [s] });
  }

  return (
    <div className="w-64 flex-shrink-0 flex flex-col h-full bg-gray-900 text-white">
      {/* ヘッダー */}
      <div className="px-4 py-4 border-b border-gray-700">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">SRCCセンちゃんBot</p>
      </div>

      {/* New Chat ボタン */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-gray-600 hover:bg-gray-700 text-sm font-medium transition-colors text-gray-200"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          新しいチャット
        </button>
      </div>

      {/* チャット一覧 */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {sessions.length === 0 && (
          <p className="text-xs text-gray-500 px-3 py-2">履歴がありません</p>
        )}
        {grouped.map((group) => (
          <div key={group.label}>
            <p className="text-xs text-gray-500 px-2 py-1.5 mt-2 font-medium">{group.label}</p>
            {group.items.map((s) => (
              <div
                key={s.id}
                className={`group flex items-center gap-1 px-3 py-2 rounded-lg cursor-pointer mb-0.5 text-sm transition-colors ${
                  s.id === activeId
                    ? "bg-gray-700 text-white"
                    : "text-gray-300 hover:bg-gray-800"
                }`}
                onClick={() => onSelect(s.id)}
              >
                <svg className="w-3.5 h-3.5 flex-shrink-0 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <span className="flex-1 truncate">{s.title}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(s.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity p-0.5 rounded"
                  title="削除"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* フッター */}
      <div className="p-3 border-t border-gray-700 space-y-2">
        <button
          onClick={() => {
            if (confirm("すべての履歴を削除しますか？")) onClearAll();
          }}
          className="w-full text-xs text-gray-500 hover:text-red-400 transition-colors py-1"
        >
          履歴をすべて削除
        </button>
        <p className="text-xs text-gray-600 text-center">履歴はこの端末に保存されます</p>
      </div>
    </div>
  );
}
