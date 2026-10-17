import { Composition } from 'remotion';

import { DemoB, DEMO_B_SECONDS, type DemoBProps } from './videos/demo-b/DemoB';

export function Root() {
  return (
    <Composition
      id="DemoB"
      component={DemoB}
      width={1920}
      height={1080}
      fps={60}
      durationInFrames={Math.round(DEMO_B_SECONDS * 60)}
      defaultProps={{ fps: 60, debug: false } satisfies DemoBProps}
      calculateMetadata={({ props }) => ({
        fps: props.fps,
        durationInFrames: Math.round(DEMO_B_SECONDS * props.fps),
      })}
    />
  );
}
