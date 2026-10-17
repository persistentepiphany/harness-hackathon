// Small monochrome icons (inline SVG, currentColor, 14px grid) for the outcome dimensions and
// the score info affordance.

import type { DimensionId } from '@/lib/types';

const P = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.3, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };

function Svg({ children, size = 14, title }: { children: React.ReactNode; size?: number; title?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" aria-hidden={title ? undefined : true} role={title ? 'img' : undefined} className="flex-none">
      {title && <title>{title}</title>}
      {children}
    </svg>
  );
}

/** Icon per dimension: MSA rows (inputs), target (exposure), ruler (physical validity), link (chemical plausibility), spring (stability), check-shield (corroboration); gauge for confidence. */
export function DimensionIcon({ id, size }: { id: DimensionId | string; size?: number }) {
  switch (id) {
    case 'inputs':
      return (
        <Svg size={size}>
          <path {...P} d="M2 3.5h10M2 6h7.5M2 8.5h10M2 11h5.5" />
        </Svg>
      );
    case 'exposure':
      return (
        <Svg size={size}>
          <circle {...P} cx="7" cy="7" r="5" />
          <circle {...P} cx="7" cy="7" r="2" />
        </Svg>
      );
    case 'physical_validity':
      return (
        <Svg size={size}>
          <path {...P} d="M1.8 9.6 9.6 1.8l2.6 2.6-7.8 7.8z" />
          <path {...P} d="M4.4 7l1.2 1.2M6.1 5.3l.9.9M7.8 3.6l1.2 1.2" />
        </Svg>
      );
    case 'stability':
      return (
        <Svg size={size}>
          <path {...P} d="M7 1.5v1.6l3 1-6 1.6 6 1.6-6 1.6 3 1v2.6" />
          <circle {...P} cx="7" cy="12.4" r=".2" />
        </Svg>
      );
    case 'chemical_plausibility':
      return (
        <Svg size={size}>
          <path {...P} d="M5.8 8.2 8.2 5.8" />
          <path {...P} d="M6.6 4.2l1.1-1.1a2.2 2.2 0 0 1 3.2 3.2L9.8 7.4M7.4 9.8l-1.1 1.1a2.2 2.2 0 0 1-3.2-3.2l1.1-1.1" />
        </Svg>
      );
    case 'confidence':
      return (
        <Svg size={size}>
          <path {...P} d="M2 10.5a5 5 0 1 1 10 0" />
          <path {...P} d="M7 10.5 9.4 6.6" />
        </Svg>
      );
    case 'corroboration':
      return (
        <Svg size={size}>
          <path {...P} d="M7 1.6 11.6 3.3v3.4c0 2.7-1.9 4.8-4.6 5.7C4.3 11.5 2.4 9.4 2.4 6.7V3.3z" />
          <path {...P} d="m4.9 7 1.5 1.5 2.8-3" />
        </Svg>
      );
    default:
      return (
        <Svg size={size}>
          <circle {...P} cx="7" cy="7" r="4.5" />
        </Svg>
      );
  }
}

export function InfoIcon({ size = 11 }: { size?: number }) {
  return (
    <Svg size={size}>
      <circle {...P} cx="7" cy="7" r="5.6" />
      <path {...P} d="M7 6.3v3.6" />
      <circle cx="7" cy="4.3" r=".8" fill="currentColor" />
    </Svg>
  );
}
