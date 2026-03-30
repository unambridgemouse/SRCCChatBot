"use client";

import { useState } from "react";

type Source = {
  doc_id: string;
  type: string;
  title: string;
  score: number;
  source?: string;
};

type Props = {
  expandedQuery?: string;
  sources?: Source[];
  entities?: string[];
  systemPrompt?: string;
};

export default function DebugPanel({ expandedQuery, sources, entities, systemPrompt }: Props) {
  const [open, setOpen] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false);

  return (
    <div className="mt-2 text-[11px] border border-gray-200 rounded-lg overflow-hidden">
      {/* ヘッダー（クリックで開閉） */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-1.5 bg-gray-50 hover:bg-gray-100 text-gray-500 transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <span>🔍</span>
          <span className="font-medium">思考プロセス</span>
        </span>
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-3 py-2 space-y-3 bg-white">

          {/* クエリ展開 */}
          {expandedQuery && (
            <section>
              <p className="font-semibold text-gray-600 mb-1">クエリ展開</p>
              <p className="text-gray-700 bg-gray-50 rounded px-2 py-1 break-all">
                {expandedQuery}
              </p>
            </section>
          )}

          {/* 参照ドキュメント */}
          {sources && sources.length > 0 && (
            <section>
              <p className="font-semibold text-gray-600 mb-1">
                参照ドキュメント（{sources.length}件）
              </p>
              <table className="w-full text-left">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-100">
                    <th className="pb-0.5 pr-2 font-medium">スコア</th>
                    <th className="pb-0.5 pr-2 font-medium">種別</th>
                    <th className="pb-0.5 pr-2 font-medium">ID</th>
                    <th className="pb-0.5 font-medium">ソース</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((s) => (
                    <tr key={s.doc_id} className="border-b border-gray-50 last:border-0">
                      <td className="py-0.5 pr-2">
                        <span
                          className={`font-mono font-bold ${
                            s.score >= 0.85
                              ? "text-green-600"
                              : s.score >= 0.6
                              ? "text-yellow-600"
                              : "text-gray-400"
                          }`}
                        >
                          {s.score.toFixed(3)}
                        </span>
                      </td>
                      <td className="py-0.5 pr-2">
                        <span
                          className={`px-1 rounded ${
                            s.type === "faq"
                              ? "bg-blue-50 text-blue-600"
                              : "bg-purple-50 text-purple-600"
                          }`}
                        >
                          {s.type}
                        </span>
                      </td>
                      <td className="py-0.5 pr-2 font-mono text-gray-500">{s.doc_id}</td>
                      <td className="py-0.5 text-gray-400 truncate max-w-[120px]">
                        {s.source ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {/* 抽出用語 */}
          {entities && entities.length > 0 && (
            <section>
              <p className="font-semibold text-gray-600 mb-1">抽出用語</p>
              <div className="flex flex-wrap gap-1">
                {entities.map((e) => (
                  <span
                    key={e}
                    className="bg-yellow-50 text-yellow-700 border border-yellow-200 px-1.5 py-0.5 rounded-full"
                  >
                    {e}
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* Claudeへのプロンプト全文 */}
          {systemPrompt && (
            <section>
              <button
                onClick={() => setPromptOpen((v) => !v)}
                className="font-semibold text-gray-600 flex items-center gap-1 hover:text-gray-800"
              >
                <span>Claudeへのプロンプト全文</span>
                <span className="text-gray-400">{promptOpen ? "▲" : "▼"}</span>
              </button>
              {promptOpen && (
                <pre className="mt-1 text-gray-600 bg-gray-50 rounded px-2 py-1.5 overflow-x-auto whitespace-pre-wrap break-all leading-relaxed">
                  {systemPrompt}
                </pre>
              )}
            </section>
          )}

        </div>
      )}
    </div>
  );
}
