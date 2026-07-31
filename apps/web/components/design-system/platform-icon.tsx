import type { Platform } from "@rqt21/contracts";
import { cn } from "@/lib/utils";

// Simplified, recognizable renditions of each network's mark — not traced
// from official brand assets, just close enough silhouettes so the picker
// reads as "real logos" at a glance instead of generic placeholder icons.
function InstagramGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="2.5" y="2.5" width="19" height="19" rx="6" stroke="currentColor" strokeWidth="2" />
      <circle cx="12" cy="12" r="4.3" stroke="currentColor" strokeWidth="2" />
      <circle cx="17.4" cy="6.6" r="1.15" fill="currentColor" />
    </svg>
  );
}

function FacebookGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M15.5 8.5H13.6c-.4 0-.6.3-.6.7v1.8h2.4l-.3 2.4h-2.1V21h-2.8v-7.6H8.4v-2.4H10V9c0-2.1 1.2-3.5 3.5-3.5h2v3z" />
    </svg>
  );
}

function TikTokGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M15.6 3c.3 1.9 1.5 3.3 3.4 3.6v2.6c-1.2.1-2.4-.3-3.4-1v6.4c0 3-2.4 5.4-5.4 5.4S4.8 17.6 4.8 14.6c0-2.9 2.3-5.3 5.2-5.4v2.7a2.7 2.7 0 1 0 2.7 2.7V3h2.9z" />
    </svg>
  );
}

function YouTubeGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="2.5" y="5.5" width="19" height="13" rx="4" stroke="currentColor" strokeWidth="2" />
      <path d="M10.5 9.3v5.4l4.7-2.7-4.7-2.7z" fill="currentColor" />
    </svg>
  );
}

function WhatsAppGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 3a9 9 0 0 0-7.8 13.5L3 21l4.6-1.2A9 9 0 1 0 12 3zm0 2a7 7 0 0 1 5.9 10.7l-.2.4.9 2.6-2.7-.8-.4.2A7 7 0 1 1 12 5z" />
      <path d="M9.2 8.3c.2-.5.4-.5.6-.5h.5c.2 0 .4 0 .5.4.2.4.6 1.4.7 1.5.1.1.1.3 0 .4-.1.2-.2.3-.3.4l-.4.4c-.1.1-.3.3-.1.6.2.4.9 1.4 1.9 2.3 1.3 1.1 2.3 1.4 2.7 1.6.3.1.5.1.7-.1l.6-.7c.2-.3.4-.2.6-.1l1.5.7c.2.1.4.2.4.4.1.6-.2 1.4-.7 1.8-.5.5-1.6.9-3.2.4-1.7-.5-3.4-1.7-4.7-3.1-1.2-1.3-2-2.7-2.3-3.6-.3-.9-.2-1.7.2-2.3.3-.5.6-.9.9-1z" />
    </svg>
  );
}

function EmailGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="2.5" y="5" width="19" height="14" rx="3" stroke="currentColor" strokeWidth="2" />
      <path d="M4 7l8 6 8-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function WebGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
      <ellipse cx="12" cy="12" rx="4" ry="9" stroke="currentColor" strokeWidth="2" />
      <path d="M3 12h18" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

function MetaAdsGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path
        d="M6.5 8c-2 0-3.5 2-3.5 4.5S4.5 17 6.5 17c1.6 0 2.8-1.3 3.9-3 1.1 1.7 2.3 3 3.9 3 2 0 3.5-2 3.5-4.5S16.3 8 14.3 8c-1.6 0-2.8 1.3-3.9 3C9.3 9.3 8.1 8 6.5 8z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function OtherGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path
        d="M12 3l1.8 5.6H20l-4.9 3.5L17 18l-5-3.6L7 18l1.9-5.9L4 8.6h6.2z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export const PLATFORM_BRAND: Record<
  Platform,
  { label: string; Icon: (props: { className?: string }) => JSX.Element; className: string }
> = {
  INSTAGRAM: {
    label: "Instagram",
    Icon: InstagramGlyph,
    className: "bg-gradient-to-br from-amber-400 via-fuchsia-500 to-indigo-500 text-white",
  },
  FACEBOOK: {
    label: "Facebook",
    Icon: FacebookGlyph,
    className: "bg-[#1877F2] text-white",
  },
  TIKTOK: {
    label: "TikTok",
    Icon: TikTokGlyph,
    className: "bg-black text-white",
  },
  YOUTUBE: {
    label: "YouTube",
    Icon: YouTubeGlyph,
    className: "bg-[#FF0000] text-white",
  },
  WHATSAPP: {
    label: "WhatsApp",
    Icon: WhatsAppGlyph,
    className: "bg-[#25D366] text-white",
  },
  EMAIL: {
    label: "Email",
    Icon: EmailGlyph,
    className: "bg-gradient-to-br from-slate-500 to-slate-700 text-white",
  },
  WEB: {
    label: "Web",
    Icon: WebGlyph,
    className: "bg-gradient-to-br from-teal-500 to-cyan-600 text-white",
  },
  META_ADS: {
    label: "Meta Ads",
    Icon: MetaAdsGlyph,
    className: "bg-gradient-to-br from-[#0668E1] to-[#0A2FFF] text-white",
  },
  OTHER: {
    label: "Otra",
    Icon: OtherGlyph,
    className: "bg-gradient-to-br from-zinc-500 to-zinc-700 text-white",
  },
};

export function PlatformIcon({
  platform,
  size = "md",
  className,
}: {
  platform: Platform;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const brand = PLATFORM_BRAND[platform];
  const dims = size === "sm" ? "h-8 w-8" : size === "lg" ? "h-14 w-14" : "h-11 w-11";
  const iconDims = size === "sm" ? "h-4 w-4" : size === "lg" ? "h-7 w-7" : "h-5.5 w-5.5";
  const Icon = brand.Icon;
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-2xl shadow-sm",
        dims,
        brand.className,
        className,
      )}
    >
      <Icon className={iconDims} />
    </span>
  );
}
