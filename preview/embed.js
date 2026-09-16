/**
 * PLOT: The Cultural Atlas - Embed Auto-Height Synchronizer
 * Zero-dependency helper script for blogs, Substack, Medium, and forums.
 * Listens for 'plot:resize' postMessage events from embedded PLOT iframes
 * and dynamically adjusts their height to eliminate double scrollbars.
 */
(function() {
  'use strict';

  function handlePlotMessage(event) {
    if (!event || !event.data || typeof event.data !== 'object') return;
    
    // Validate message protocol
    if (event.data.type === 'plot:resize' && typeof event.data.height === 'number') {
      const targetHeight = Math.max(280, Math.min(event.data.height, 2400));
      const iframes = document.querySelectorAll('iframe[src*="/embed"]');
      
      for (let i = 0; i < iframes.length; i++) {
        const frame = iframes[i];
        if (frame.contentWindow === event.source) {
          frame.style.height = targetHeight + 'px';
          frame.style.transition = 'height 0.18s cubic-bezier(0.16, 1, 0.3, 1)';
          break;
        }
      }
    }
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('message', handlePlotMessage, false);
  }
})();
