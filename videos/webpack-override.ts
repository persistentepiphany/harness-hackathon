import type { WebpackOverrideFn } from '@remotion/bundler';

/**
 * Film B uses no Tailwind and imports nothing from web/, so the override stays empty on purpose:
 * the web app's Tailwind is never resolved from this workspace. Twins copy the product's classes
 * as inline styles (see src/videos/demo-b/ui/).
 */
export const webpackOverride: WebpackOverrideFn = (config) => config;
