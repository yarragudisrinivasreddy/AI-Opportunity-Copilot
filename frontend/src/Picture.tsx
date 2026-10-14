/** Same-origin responsive WebP. Hero uses full lean srcset; others use 800px lean files. */
import type { ImgHTMLAttributes } from "react";

type ImgKind = "hero-work" | "factory-network" | "compare-pillars" | "privacy-glass" | "workshop-dawn";

const META: Record<ImgKind, { w: number; h: number; files: { src: string; w: number }[] }> = {
  "hero-work": {
    w: 1600, h: 900,
    files: [
      { src: "/img/hero-work-400.webp", w: 400 },
      { src: "/img/hero-work-800.webp", w: 800 },
      { src: "/img/hero-work-1600.webp", w: 1600 },
    ],
  },
  "factory-network": { w: 800, h: 450, files: [{ src: "/img/factory-network-800.webp", w: 800 }] },
  "compare-pillars": { w: 800, h: 450, files: [{ src: "/img/compare-pillars-800.webp", w: 800 }] },
  "privacy-glass": { w: 800, h: 450, files: [{ src: "/img/privacy-glass-800.webp", w: 800 }] },
  "workshop-dawn": { w: 800, h: 450, files: [{ src: "/img/workshop-dawn-800.webp", w: 800 }] },
};

export function Picture({
  kind, className, alt = "", sizes, priority = false,
}: {
  kind: ImgKind; className?: string; alt?: string; sizes?: string; priority?: boolean;
}) {
  const m = META[kind];
  const srcSet = m.files.map((f) => `${f.src} ${f.w}w`).join(", ");
  const fallback = m.files[m.files.length - 1].src;
  return (
    <img
      className={className}
      src={fallback}
      srcSet={srcSet}
      sizes={sizes ?? (priority ? "100vw" : "(max-width: 768px) 100vw, 800px")}
      width={m.w}
      height={m.h}
      alt={alt}
      loading={priority ? "eager" : "lazy"}
      decoding={priority ? "sync" : "async"}
      {...(priority ? { fetchpriority: "high" } as ImgHTMLAttributes<HTMLImageElement> : {})}
    />
  );
}
