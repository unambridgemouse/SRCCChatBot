import SourceCitation from "./SourceCitation";
import DebugPanel from "./DebugPanel";

type Source = {
  doc_id: string;
  type: string;
  title: string;
  score: number;
  source?: string;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  entities?: string[];
  isStreaming?: boolean;
  expandedQuery?: string;
  systemPrompt?: string;
};

// 本文を強調するセクション（ヘッダー名で判定）
const EMPHASIZED_SECTIONS = ["結論", "手順", "詳細"];

function isEmphasizedSection(heading: string) {
  return EMPHASIZED_SECTIONS.some((s) => heading.includes(s));
}

/** **text** をインライン太字に変換して React 要素の配列を返す */
function renderInline(text: string, key: string | number) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${key}-${i}`}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

/** テキスト全体を行単位でパースし、見出し行はグレー小さめ・結論/手順の本文は強調表示 */
function renderContent(content: string) {
  const lines = content.split("\n");
  let emphasized = false;

  return lines.map((line, i) => {
    const isLast = i === lines.length - 1;
    const headingMatch = line.match(/^\*\*(.+)\*\*$/);

    if (headingMatch) {
      emphasized = isEmphasizedSection(headingMatch[1]);
      return (
        <div key={i} className="text-xs font-semibold text-gray-400 mt-3 mb-0.5 uppercase tracking-wide">
          {headingMatch[1]}
        </div>
      );
    }

    if (emphasized && line.trim() !== "") {
      return (
        <span key={i} className="font-semibold text-gray-900">
          {renderInline(line, i)}
          {!isLast && "\n"}
        </span>
      );
    }

    return (
      <span key={i}>
        {renderInline(line, i)}
        {!isLast && "\n"}
      </span>
    );
  });
}

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm ${
          isUser
            ? "bg-blue-600 text-white rounded-br-sm"
            : "bg-white text-gray-800 rounded-bl-sm border border-gray-100"
        }`}
      >
        {/* メッセージ本文 */}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {isUser ? message.content : renderContent(message.content)}
          {message.isStreaming && (
            <span className="inline-block w-1.5 h-4 bg-gray-400 ml-0.5 animate-pulse" />
          )}
        </div>

        {/* 抽出用語タグ（アシスタントのみ） */}
        {!isUser && message.entities && message.entities.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.entities.map((e) => (
              <span
                key={e}
                className="text-[10px] bg-yellow-50 text-yellow-700 border border-yellow-200 px-1.5 py-0.5 rounded-full"
              >
                {e}
              </span>
            ))}
          </div>
        )}

        {/* 引用元 */}
        {!isUser && message.sources && <SourceCitation sources={message.sources} />}

        {/* デバッグパネル（アシスタントのみ・ストリーミング完了後） */}
        {!isUser && !message.isStreaming && (
          message.expandedQuery || (message.sources && message.sources.length > 0) || message.systemPrompt
        ) && (
          <DebugPanel
            expandedQuery={message.expandedQuery}
            sources={message.sources}
            entities={message.entities}
            systemPrompt={message.systemPrompt}
          />
        )}
      </div>
    </div>
  );
}
