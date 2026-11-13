"use client";

import { animate, useInView, useMotionValue, useTransform, motion } from "motion/react";
import { useEffect, useRef } from "react";

/** A number that counts up once when it comes into view. */
export function Contador({ valor, className }: { valor: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const visto = useInView(ref, { once: true });
  const atual = useMotionValue(0);
  const texto = useTransform(atual, (v) => Math.round(v).toLocaleString("pt-BR"));
  useEffect(() => {
    if (!visto) return;
    const a = animate(atual, valor, { duration: 1.1, ease: [0.2, 0.8, 0.2, 1] });
    return () => a.stop();
  }, [visto, valor, atual]);
  return (
    <motion.span ref={ref} className={`tabular-nums ${className ?? ""}`}>
      {texto}
    </motion.span>
  );
}
