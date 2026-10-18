// Screen layout of film B at 1920x1080. The product is laid out in its own CSS pixels (a 1440 px
// wide page, 13 px base text) and filmed through a camera, so 13 px reads at 24 px and up.

export const FRAME = { width: 1920, height: 1080 } as const;

/** The product's top nav, drawn at 1.5x: 44 product px tall, 1280 product px wide. */
export const NAV = { scale: 1.5, height: 66, width: 1280 } as const;

/** Where the camera's picture of the product goes. */
export const VIEW = { x: 0, y: NAV.height, w: FRAME.width, h: 940 - NAV.height } as const;

/** The caption band under the picture; the UI never reaches into it. */
export const CAPTION = { top: 940, height: 140, textY: 990, tagY: 1046 } as const;

/** Product page width (web/design/reference-shots are 1440 wide). */
export const PAGE_W = 1440;
