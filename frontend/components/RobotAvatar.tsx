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
        borderRadius: "22px",
        overflow: "hidden",
        boxShadow: isTalking
          ? "0 0 16px 4px rgba(96,165,250,0.55)"
          : "0 4px 12px rgba(0,0,0,0.45)",
        transition: "box-shadow 0.3s ease",
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

        {/* ── 黒背景（角丸はコンテナ div の overflow:hidden で処理） ── */}
        <rect x="0" y="0" width="200" height="160" fill="#0f0f0f" />
        {/* 光沢 */}
        <ellipse cx="100" cy="22" rx="68" ry="14" fill="rgba(255,255,255,0.07)" />
        {/* 下部ハイライト */}
        <rect x="0" y="152" width="200" height="8" rx="4" fill="rgba(255,255,255,0.04)" />

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
