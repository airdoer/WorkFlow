/**
 * Simple event bus for node execution events.
 * Used to communicate between BaseNode (which runs nodes) and FlowEditor (which handles cascade).
 */

type Listener = (nodeId: string, output: any) => void;

const listeners: Listener[] = [];

export const NodeEventBus = {
  subscribe(fn: Listener) {
    listeners.push(fn);
    return () => {
      const idx = listeners.indexOf(fn);
      if (idx >= 0) listeners.splice(idx, 1);
    };
  },

  emit(nodeId: string, output: any) {
    for (const fn of listeners) {
      fn(nodeId, output);
    }
  },
};
