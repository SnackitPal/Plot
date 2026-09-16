/**
 * PLOT: The Cultural Atlas — Chrome Extension Content Script
 * Extracts high-signal deliberation context (titles, topics, canonical URLs)
 * from Reddit, YouTube, Substack, and general articles.
 */

(function () {
  // Tracking query parameters to strip
  const TRACKING_PARAMS = new Set([
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'ref', 'fbclid', 'gclid', 'igshid', 'si', 'feature'
  ]);

  function normalizeUrl(rawUrl) {
    try {
      const parsed = new URL(rawUrl);
      const searchParams = new URLSearchParams();
      
      // Preserve essential query params (e.g. YouTube v=...)
      for (const [key, val] of parsed.searchParams.entries()) {
        const lowerKey = key.toLowerCase();
        if (!TRACKING_PARAMS.has(lowerKey) && !lowerKey.startsWith('utm_')) {
          searchParams.append(key, val);
        }
      }

      let pathname = parsed.pathname;
      if (pathname.length > 1 && pathname.endsWith('/')) {
        pathname = pathname.slice(0, -1);
      }

      const queryString = searchParams.toString() ? `?${searchParams.toString()}` : '';
      return `${parsed.protocol}//${parsed.hostname}${pathname}${queryString}`;
    } catch (e) {
      return rawUrl;
    }
  }

  function extractPageContext() {
    const rawUrl = window.location.href;
    const hostname = window.location.hostname.toLowerCase();
    let platform = 'WEB';
    let title = '';
    let excerpt = '';
    let authorOrChannel = '';
    let subreddit = '';

    // 1. Check Canonical Link Tag
    const canonicalEl = document.querySelector('link[rel="canonical"]');
    const canonicalHref = canonicalEl ? canonicalEl.href : '';
    const canonicalUrl = normalizeUrl(canonicalHref || rawUrl);

    // 2. Platform Specific Extraction
    if (hostname.includes('reddit.com')) {
      platform = 'REDDIT';
      
      // Subreddit extraction
      const subMatch = window.location.pathname.match(/\/r\/([^/]+)/i);
      subreddit = subMatch ? `r/${subMatch[1]}` : '';

      // Post Title
      const h1El = document.querySelector('h1[slot="title"]') || document.querySelector('h1');
      title = h1El ? h1El.textContent.trim() : document.title.replace(/ : r\/.*/, '').replace(/ - Reddit$/, '');

      // Post Body / Text
      const bodyEl = document.querySelector('div[slot="text-body"]') || document.querySelector('[data-test-id="post-content"]');
      excerpt = bodyEl ? bodyEl.textContent.trim().slice(0, 300) : '';

      // Author
      const authorEl = document.querySelector('a[href*="/user/"]');
      authorOrChannel = authorEl ? authorEl.textContent.trim() : '';

    } else if (hostname.includes('youtube.com') || hostname.includes('youtu.be')) {
      platform = 'YOUTUBE';

      // Video Title
      const ytTitleEl = document.querySelector('h1.ytd-watch-metadata') || document.querySelector('h1.title') || document.querySelector('h1');
      title = ytTitleEl ? ytTitleEl.textContent.trim() : document.title.replace(/ - YouTube$/, '');

      // Channel Name
      const channelEl = document.querySelector('#channel-name a') || document.querySelector('#owner-name a');
      authorOrChannel = channelEl ? channelEl.textContent.trim() : '';

      // Description Excerpt
      const descEl = document.querySelector('#description-inline-expander') || document.querySelector('#description');
      excerpt = descEl ? descEl.textContent.trim().slice(0, 300) : '';

    } else if (hostname.includes('substack.com')) {
      platform = 'SUBSTACK';
      
      const h1 = document.querySelector('h1.post-title') || document.querySelector('h1');
      title = h1 ? h1.textContent.trim() : document.title;

      const subDesc = document.querySelector('h3.subtitle') || document.querySelector('meta[name="description"]');
      excerpt = subDesc ? (subDesc.content || subDesc.textContent || '').trim().slice(0, 300) : '';

    } else {
      // General News / Blogs / Web
      const ogTitle = document.querySelector('meta[property="og:title"]');
      const h1 = document.querySelector('h1');
      title = (ogTitle && ogTitle.content) ? ogTitle.content.trim() : (h1 ? h1.textContent.trim() : document.title);

      const ogDesc = document.querySelector('meta[property="og:description"]') || document.querySelector('meta[name="description"]');
      const p = document.querySelector('article p') || document.querySelector('p');
      excerpt = (ogDesc && ogDesc.content) ? ogDesc.content.trim().slice(0, 300) : (p ? p.textContent.trim().slice(0, 300) : '');

      const authorMeta = document.querySelector('meta[name="author"]') || document.querySelector('meta[property="article:author"]');
      authorOrChannel = authorMeta ? authorMeta.content.trim() : '';
    }

    return {
      url: rawUrl,
      canonical_url: canonicalUrl,
      platform: platform,
      title: title || document.title || 'Web Discussion',
      excerpt: excerpt || '',
      author_or_channel: authorOrChannel,
      subreddit: subreddit
    };
  }

  // Listen for extraction requests from sidepanel or background
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message && message.type === 'PLOT_EXTRACT_CONTENT') {
      const context = extractPageContext();
      sendResponse({ success: true, data: context });
      return true;
    }
  });

  // Expose global helper for testing environment
  if (typeof window !== 'undefined') {
    window.__PLOT_EXTRACT_CONTEXT = extractPageContext;
  }
})();
