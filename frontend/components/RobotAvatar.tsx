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
          {/* 碁盤の木目グラデーション */}
          <linearGradient id="woodGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="#D9A84E" />
            <stop offset="50%"  stopColor="#C8923A" />
            <stop offset="100%" stopColor="#B07828" />
          </linearGradient>
          {/* 碁盤グリッドパターン（格子線） */}
          <pattern id="goGrid" x="4" y="4" width="16" height="12.5" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="16"  y2="0"    stroke="#5C3010" strokeWidth="0.7" opacity="0.55" />
            <line x1="0" y1="0" x2="0"   y2="12.5" stroke="#5C3010" strokeWidth="0.7" opacity="0.55" />
          </pattern>
          {/* クリップパス（角丸に合わせてパターンを切り抜く） */}
          <clipPath id="boardClip">
            <rect x="4" y="4" width="192" height="152" rx="38" ry="38" />
          </clipPath>
        </defs>

        {/* ── 本体：碁盤背景 ── */}
        <rect x="4" y="4" width="192" height="152" rx="38" ry="38" fill="url(#woodGrad)" />
        {/* 格子線（クリップで角丸の外にはみ出さない） */}
        <rect x="0" y="0" width="200" height="160" fill="url(#goGrid)" clipPath="url(#boardClip)" />
        {/* 枠線 */}
        <rect x="4" y="4" width="192" height="152" rx="38" ry="38" fill="none" stroke="#7A4A18" strokeWidth="2.5" />
        {/* 光沢 */}
        <ellipse cx="100" cy="28" rx="68" ry="14" fill="rgba(255,255,255,0.12)" />

        {/* ── 左目 ── */}
        <g opacity={blink ? 0 : 1} style={{ transition: "opacity 0.05s" }}>
          <circle cx="48" cy="74" r="20" fill="rgba(255,255,255,0.25)" stroke="#3A2008" strokeWidth="3.5" />
          <g stroke="#3A2008" strokeWidth="2.5" strokeLinecap="round">
            <line x1="33" y1="57" x2="39" y2="63" />
            <line x1="39" y1="57" x2="33" y2="63" />
          </g>
        </g>

        {/* ── 右目 ── */}
        <g opacity={blink ? 0 : 1} style={{ transition: "opacity 0.05s" }}>
          <circle cx="152" cy="74" r="20" fill="rgba(255,255,255,0.25)" stroke="#3A2008" strokeWidth="3.5" />
          <g stroke="#3A2008" strokeWidth="2.5" strokeLinecap="round">
            <line x1="137" y1="57" x2="143" y2="63" />
            <line x1="143" y1="57" x2="137" y2="63" />
          </g>
        </g>

        {/* ── 口 ── */}
        {isTalking ? (
          <ellipse
            cx="100"
            cy="114"
            rx="20"
            ry="11"
            fill="#3A2008"
            className="mouth-talking"
          />
        ) : (
          <path
            d="M 76 108 Q 100 126 124 108"
            stroke="#3A2008"
            fill="none"
            strokeWidth="4"
            strokeLinecap="round"
          />
        )}

        {/* ── 右下スター装飾 ── */}
        <g fill="#7A4A18" transform="translate(176, 144)">
          <polygon points="0,-5 1.5,-1.5 5,-1.5 2.5,1 3.5,4.5 0,2.5 -3.5,4.5 -2.5,1 -5,-1.5 -1.5,-1.5" />
        </g>
      </svg>
    </div>
  );
}
