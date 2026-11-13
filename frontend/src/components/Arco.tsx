"use client";

import { motion } from "motion/react";

import { Contador } from "./Contador";

const R = 60;
const VOLTA = 2 * Math.PI * R;

/** The fit score: an arc that fills up to the value, the number counting with it. */
export function Arco({ nota }: { nota: number }) {
  return (
    <div className="relative size-[140px] shrink-0">
      <svg viewBox="0 0 140 140" className="size-full -rotate-90">
        <circle cx="70" cy="70" r={R} fill="none" strokeWidth="10" className="stroke-verde-suave" />
        <motion.circle
          key={nota}
          cx="70"
          cy="70"
          r={R}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          className={nota >= 60 ? "stroke-verde" : "stroke-ambar"}
          strokeDasharray={VOLTA}
          initial={{ strokeDashoffset: VOLTA }}
          animate={{ strokeDashoffset: VOLTA * (1 - nota / 100) }}
          transition={{ duration: 1.3, ease: [0.2, 0.8, 0.2, 1], delay: 0.1 }}
        />
      </svg>
      <span className={`absolute inset-0 grid place-items-center font-display text-[42px] font-bold ${nota >= 60 ? "text-verde" : "text-ambar"}`}>
        <Contador key={nota} valor={nota} />
      </span>
      <span className="absolute -bottom-6 w-full text-center text-xs text-apagado">de encaixe</span>
    </div>
  );
}
