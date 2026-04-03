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

  const MIN_SCORE = 0.01;

  // source / source2 ごとに {url or name, label} を収集・重複除去
  const seen = new Set<string>();
  const manuals: { value: string; label: string }[] = [];

  for (const s of sources) {
    if (s.score < MIN_SCORE && s.type !== "store") continue;
    for (const [val, lbl] of [
      [s.source, s.source_label],
      [s.source2, s.source2_label],
    ] as [string | undefined, string | undefined][]) {
      if (!val || seen.has(val)) continue;
      seen.add(val);
      manuals.push({ value: val, label: lbl ?? val });
    }
  }

  if (manuals.length === 0) return null;

  return (
    <div className="mt-3 pt-3 border-t border-gray-200">
      <p className="text-xs font-semibold text-gray-500 mb-1">参照マニュアル</p>
      <ul className="space-y-1">
        {manuals.map(({ value, label }) => {
          const isUrl = value.startsWith("http://") || value.startsWith("https://");
          return (
            <li key={value} className="flex items-center gap-2 text-xs text-gray-600">
              <svg className="w-3 h-3 flex-shrink-0 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {isUrl ? (
                <a href={value} target="_blank" rel="noopener noreferrer"
                  className="text-blue-500 hover:underline">
                  {label}
                </a>
              ) : (
                <span>{label}</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
