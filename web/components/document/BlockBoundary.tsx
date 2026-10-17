'use client';

// Fail soft: a report block that cannot render this record (for example a stats block in a shape
// the block does not read yet) shows one muted line instead of taking the document down.

import { Component, type ReactNode } from 'react';

interface Props {
  /** Block name for the fallback line and data-block. */
  name: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class BlockBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="border-t border-line pt-1 text-[8pt] text-muted" data-testid="block-error" data-block={this.props.name} title={this.state.error.message}>
          {this.props.name} · cannot be shown for this record
        </div>
      );
    }
    return this.props.children;
  }
}
