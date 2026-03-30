"use client";

import { useEffect, useState } from "react";

type Props = {
  isTalking: boolean;
  size?: number;
};

export default function RobotAvatar({ isTalking, size = 160 }: Props) {
  const [blink, setBlink] = useState(false);

  // 定期的なまばたき（待機中のみ）
  useEffect(() => {
    if (isTalking) return;
    const schedule = () =>
      setTimeout(() => {
        setBlink(true);
        setTimeout(() => {
          setBlink(false);
          timer = schedule();
        }, 120);
      }, 2500 + Math.random() * 2000);

    let timer = schedule();
    return () => clearTimeout(timer);
  }, [isTalking]);

  const h = (size * 160) / 200; // aspect ratio 200:160

  return (
    <div
      style={{
        width: size,
        height: h,
        filter: isTalking
          ? "drop-shadow(0 0 12px rgba(96, 165, 250, 0.6))"
          : "drop-shadow(0 4px 8px rgba(0,0,0,0.4))",
        transition: "filter 0.3s ease",
        animation: isTalking ? "robotBounce 0.5s ease-in-out infinite" : "none",
      }}
    >
      <svg
        width={size}
        height={h}
        viewBox="0 0 200 160"
        xmlns="http://www.w3.org/2000/svg"
      >
        <style>{`
          @keyframes robotBounce {
            0%, 100% { transform: translateY(0px); }
            50%       { transform: translateY(-4px); }
          }
          @keyframes mouthTalk {
            0%, 100% { transform: scaleY(0.25); }
            30%       { transform: scaleY(1); }
            60%       { transform: scaleY(0.5); }
            80%       { transform: scaleY(0.9); }
          }
          .mouth-talking {
            transform-box: fill-box;
            transform-origin: center;
            animation: mouthTalk 0.35s ease-in-out infinite;
          }
        `}</style>

        {/* ── 本体 ── */}
        <rect x="4" y="4" width="192" height="152" rx="38" ry="38" fill="#0f0f0f" />
        {/* 光沢 */}
        <ellipse cx="100" cy="28" rx="68" ry="16" fill="rgba(255,255,255,0.07)" />
        {/* 下部の台座的ハイライト */}
        <rect x="4" y="148" width="192" height="8" rx="8" fill="rgba(255,255,255,0.04)" />

        {/* ── 左目 ── */}
        <g opacity={blink ? 0 : 1} style={{ transition: "opacity 0.05s" }}>
          {/* リング */}
          <circle cx="48" cy="74" r="20" fill="none" stroke="#d4d4d4" strokeWidth="3.5" />
          {/* × マーク（リング左上） */}
          <g stroke="#d4d4d4" strokeWidth="2.5" strokeLinecap="round">
            <line x1="33" y1="57" x2="39" y2="63" />
            <line x1="39" y1="57" x2="33" y2="63" />
          </g>
        </g>

        {/* ── 右目 ── */}
        <g opacity={blink ? 0 : 1} style={{ transition: "opacity 0.05s" }}>
          {/* リング */}
          <circle cx="152" cy="74" r="20" fill="none" stroke="#d4d4d4" strokeWidth="3.5" />
          {/* × マーク（リング左上） */}
          <g stroke="#d4d4d4" strokeWidth="2.5" strokeLinecap="round">
            <line x1="137" y1="57" x2="143" y2="63" />
            <line x1="143" y1="57" x2="137" y2="63" />
          </g>
        </g>

        {/* ── 口 ── */}
        {isTalking ? (
          /* 話し中: 楕円が縦に開閉 */
          <ellipse
            cx="100"
            cy="114"
            rx="20"
            ry="11"
            fill="#d4d4d4"
            className="mouth-talking"
          />
        ) : (
          /* 待機中: スマイルカーブ */
          <path
            d="M 76 108 Q 100 126 124 108"
            stroke="#d4d4d4"
            fill="none"
            strokeWidth="4"
            strokeLinecap="round"
          />
        )}

        {/* ── 右下の小さなスターマーク（元画像に合わせた装飾）── */}
        <g fill="#333" transform="translate(176, 144)">
          <polygon points="0,-5 1.5,-1.5 5,-1.5 2.5,1 3.5,4.5 0,2.5 -3.5,4.5 -2.5,1 -5,-1.5 -1.5,-1.5" />
        </g>
      </svg>
    </div>
  );
}
