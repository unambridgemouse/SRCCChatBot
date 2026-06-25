type Source = {
  doc_id: string;
  type: string;
  title: string;
  score: number;
  source?: string;
  source_label?: string;
  source2?: string;
  source2_label?: string;
};

export default function SourceCitation({ sources }: { sources: Source[] }) {
  if (!sources || sources.length === 0) return null;

  const MIN_SCORE = 0.25;

  // Cohereリランク失敗時はスコアが均一に低くなる（RRFスコアそのまま）
  const maxScore = Math.max(...sources.map(s => s.score));
  const isCohereFallback = maxScore < 0.1;

  // source / source2 ごとに {url, label, score} を収集・重複除去
  const seen = new Set<string>();
  const manuals: { value: string; label: string; score: number }[] = [];

  const addSource = (val: string | undefined, lbl: string | undefined, score: number) => {
    if (!val || seen.has(val)) return;
    seen.add(val);
    manuals.push({ value: val, label: lbl ?? val, score });
  };

  if (isCohereFallback) {
    // Cohere失敗時：多数決（全文書の2/3以上が同じソースを持つ場合はそれを表示）
    // 無関係文書がベクトル検索でrank-0に来た場合の誤表示を防ぐ
    const srcCount: Record<string, { label: string | undefined; score: number; count: number }> = {};
    for (const s of sources) {
      for (const [val, lbl] of [
        [s.source, s.source_label],
        [s.source2, s.source2_label],
      ] as [string | undefined, string | undefined][]) {
        if (!val) continue;
        if (!srcCount[val]) srcCount[val] = { label: lbl, score: s.score, count: 0 };
        srcCount[val].count++;
      }
    }

    const majorityThreshold = Math.ceil(sources.length * 2 / 3);
    const majorityEntries = Object.entries(srcCount).filter(([, v]) => v.count >= majorityThreshold);

    if (majorityEntries.length > 0) {
      // 多数決ソースを表示
      for (const [val, info] of majorityEntries) {
        addSource(val, info.label, info.score);
      }
    } else {
      // 多数決なし → rank-0文書のsource/source2を表示
      const s = sources[0];
      addSource(s.source, s.source_label, s.score);
      addSource(s.source2, s.source2_label, s.score);
    }
  } else {
    // 通常時：MIN_SCORE以上のみ表示
    for (const s of sources) {
      if (s.score < MIN_SCORE && s.type !== "store") continue;
      addSource(s.source, s.source_label, s.score);
      addSource(s.source2, s.source2_label, s.score);
    }
  }

  if (manuals.length === 0) return null;

  return (
    <div className="mt-3 pt-3 border-t border-gray-200">
      <p className="text-xs font-semibold text-gray-500 mb-1">参照マニュアル</p>
      <ul className="space-y-1">
        {manuals.map(({ value, label, score }) => {
          const isUrl = value.startsWith("http://") || value.startsWith("https://");
          return (
            <li key={value} className="flex items-center gap-2 text-xs text-gray-600">
              <svg className="w-3 h-3 flex-shrink-0 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {isUrl ? (
                <a href={value} target="_blank" rel="noopener noreferrer"
                  className="text-blue-500 hover:underline flex-1">
                  {label}
                </a>
              ) : (
                <span className="flex-1">{label}</span>
              )}
              <span className="text-[10px] font-mono text-gray-400 ml-1">
                {score.toFixed(2)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
