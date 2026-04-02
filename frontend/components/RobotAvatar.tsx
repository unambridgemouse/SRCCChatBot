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

        <defs>
          {/* 碁盤の木目グラデーション（背景全体） */}
          <linearGradient id="woodGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="#D9A84E" />
            <stop offset="50%"  stopColor="#C8923A" />
            <stop offset="100%" stopColor="#B07828" />
          </linearGradient>
          {/* 碁盤グリッドパターン */}
          <pattern id="goGrid" x="0" y="0" width="16" height="12.5" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="16"  y2="0"    stroke="#5C3010" strokeWidth="0.8" opacity="0.6" />
            <line x1="0" y1="0" x2="0"   y2="12.5" stroke="#5C3010" strokeWidth="0.8" opacity="0.6" />
          </pattern>
        </defs>

        {/* ── 碁盤背景（SVG全体） ── */}
        <rect x="0" y="0" width="200" height="160" fill="url(#woodGrad)" />
        <rect x="0" y="0" width="200" height="160" fill="url(#goGrid)" />

        {/* ── ロボット本体（黒） ── */}
        <rect x="20" y="12" width="160" height="136" rx="30" ry="30" fill="#0f0f0f" />
        {/* 光沢 */}
        <ellipse cx="100" cy="34" rx="56" ry="13" fill="rgba(255,255,255,0.07)" />
        {/* 下部ハイライト */}
        <rect x="20" y="142" width="160" height="6" rx="6" fill="rgba(255,255,255,0.04)" />

        {/* ── 左目 ── */}
        <g opacity={blink ? 0 : 1} style={{ transition: "opacity 0.05s" }}>
          <circle cx="62" cy="78" r="18" fill="none" stroke="#d4d4d4" strokeWidth="3.5" />
          <g stroke="#d4d4d4" strokeWidth="2.5" strokeLinecap="round">
            <line x1="49" y1="63" x2="55" y2="69" />
            <line x1="55" y1="63" x2="49" y2="69" />
          </g>
        </g>

        {/* ── 右目 ── */}
        <g opacity={blink ? 0 : 1} style={{ transition: "opacity 0.05s" }}>
          <circle cx="138" cy="78" r="18" fill="none" stroke="#d4d4d4" strokeWidth="3.5" />
          <g stroke="#d4d4d4" strokeWidth="2.5" strokeLinecap="round">
            <line x1="125" y1="63" x2="131" y2="69" />
            <line x1="131" y1="63" x2="125" y2="69" />
          </g>
        </g>

        {/* ── 口 ── */}
        {isTalking ? (
          <ellipse
            cx="100"
            cy="114"
            rx="18"
            ry="10"
            fill="#d4d4d4"
            className="mouth-talking"
          />
        ) : (
          <path
            d="M 78 108 Q 100 124 122 108"
            stroke="#d4d4d4"
            fill="none"
            strokeWidth="4"
            strokeLinecap="round"
          />
        )}

        {/* ── 右下スター装飾 ── */}
        <g fill="#555" transform="translate(164, 136)">
          <polygon points="0,-5 1.5,-1.5 5,-1.5 2.5,1 3.5,4.5 0,2.5 -3.5,4.5 -2.5,1 -5,-1.5 -1.5,-1.5" />
        </g>
      </svg>
    </div>
  );
}
