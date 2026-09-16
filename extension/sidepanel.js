/**
 * PLOT: The Cultural Atlas — Chrome Extension SidePanel Controller
 * Connects to active tabs, looks up existing cultural plots,
 * drives 1-tap MECE draft generation, and provides instant stance nuance.
 */

(function () {
  // State
  let config = {
    backendUrl: 'http://localhost:8000',
    aiMode: 'edge',
    byokKey: ''
  };

  let activeTabContext = {
    url: 'https://reddit.com/r/AskEurope/comments/sample_remote_work',
    canonical_url: 'https://reddit.com/r/AskEurope/comments/sample_remote_work',
    title: 'Would you take a 30% pay cut to work remotely forever?',
    excerpt: 'Debate on commute times vs salary tradeoffs across European capitals.',
    platform: 'REDDIT'
  };

  let currentPlot = null;
  let userVote = null;
  let activeStanceTab = 'A';
  let cachedPerspectives = { 'A': [], 'B': [], 'C': [], 'D': [] };
  let currentPerspectiveId = null;

  const SYMBOL_MAP = {
    'circle': '●',
    'triangle': '▲',
    'square': '■',
    'diamond': '◆'
  };

  // Safe Audio Synthesizer
  function playClickSound(freq = 520) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      gain.gain.setValueAtTime(0.04, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.05);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.06);
    } catch (e) {}
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Storage Abstraction (chrome.storage.local with localStorage fallback)
  async function loadConfig() {
    return new Promise((resolve) => {
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.get(['backendUrl', 'aiMode', 'byokKey'], (res) => {
          if (res) {
            config.backendUrl = res.backendUrl || config.backendUrl;
            config.aiMode = res.aiMode || config.aiMode;
            config.byokKey = res.byokKey || config.byokKey;
          }
          resolve(config);
        });
      } else {
        try {
          config.backendUrl = localStorage.getItem('plot_backend_url') || config.backendUrl;
          config.aiMode = localStorage.getItem('plot_ai_mode') || config.aiMode;
          config.byokKey = localStorage.getItem('plot_byok_key') || config.byokKey;
        } catch (e) {}
        resolve(config);
      }
    });
  }

  async function saveConfig() {
    return new Promise((resolve) => {
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set(config, resolve);
      } else {
        try {
          localStorage.setItem('plot_backend_url', config.backendUrl);
          localStorage.setItem('plot_ai_mode', config.aiMode);
          localStorage.setItem('plot_byok_key', config.byokKey);
        } catch (e) {}
        resolve();
      }
    });
  }

  // Check Backend Connection
  async function checkBackendHealth() {
    const indicator = document.getElementById('backend-status-indicator');
    const textEl = document.getElementById('backend-status-text');
    try {
      const resp = await fetch(`${config.backendUrl}/api/slate/today`, { method: 'GET' });
      if (resp.ok) {
        if (textEl) textEl.textContent = 'Live';
        if (indicator) indicator.style.color = '#059669';
        return true;
      }
    } catch (e) {
      if (textEl) textEl.textContent = 'Offline';
      if (indicator) indicator.style.color = '#DC2626';
    }
    return false;
  }

  // Detect Active Tab Context
  async function detectActiveTab() {
    // 1. Check if mock context was injected via test harness
    if (window.__PLOT_MOCK_TAB) {
      activeTabContext = { ...activeTabContext, ...window.__PLOT_MOCK_TAB };
      updateContextInspectorUI();
      inspectCurrentPagePlot();
      return;
    }

    // 2. Real Chrome Extension Environment
    if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.query) {
      try {
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tabs && tabs[0] && tabs[0].url && !tabs[0].url.startsWith('chrome://')) {
          const tab = tabs[0];
          activeTabContext.url = tab.url;
          activeTabContext.canonical_url = tab.url;
          activeTabContext.title = tab.title || 'Web Discussion';

          // Try asking content script for rich context
          if (chrome.tabs.sendMessage) {
            chrome.tabs.sendMessage(tab.id, { type: 'PLOT_EXTRACT_CONTENT' }, (resp) => {
              if (chrome.runtime.lastError) {
                // Content script not loaded or restricted page
              } else if (resp && resp.success && resp.data) {
                activeTabContext = { ...activeTabContext, ...resp.data };
              }
              updateContextInspectorUI();
              inspectCurrentPagePlot();
            });
            return;
          }
        }
      } catch (err) {
        console.debug('[PLOT SidePanel] Tab query fallback:', err);
      }
    }

    updateContextInspectorUI();
    inspectCurrentPagePlot();
  }

  function updateContextInspectorUI() {
    const badgeEl = document.getElementById('page-platform-badge');
    const titleEl = document.getElementById('page-title-display');

    if (badgeEl) {
      const p = (activeTabContext.platform || 'WEB').toUpperCase();
      badgeEl.textContent = p;
      badgeEl.className = 'badge-platform shrink-0';
      if (p === 'REDDIT') badgeEl.classList.add('badge-reddit');
      else if (p === 'YOUTUBE') badgeEl.classList.add('badge-youtube');
      else if (p === 'SUBSTACK') badgeEl.classList.add('badge-substack');
      else badgeEl.classList.add('badge-web');
    }

    if (titleEl) {
      titleEl.textContent = activeTabContext.title || activeTabContext.url;
      titleEl.title = `${activeTabContext.title}\n(${activeTabContext.canonical_url})`;
    }
  }

  // Look up if a Plot exists for the current canonical URL
  async function inspectCurrentPagePlot() {
    showState('loading');
    const lookupUrl = `${config.backendUrl}/api/plots/lookup?url=${encodeURIComponent(activeTabContext.canonical_url)}`;
    
    try {
      const resp = await fetch(lookupUrl);
      if (resp.ok) {
        const data = await resp.json();
        if (data && data.exists && data.plot) {
          currentPlot = data.plot;
          renderExistingPlot(data.plot);
          loadPerspectives(data.plot.question_id);
          showState('existing');
          return;
        }
      }
    } catch (err) {
      console.warn('[PLOT SidePanel] Lookup error:', err);
    }

    // No plot found -> Cold start state
    currentPlot = null;
    showState('cold_start');
  }

  function showState(stateName) {
    const stateExisting = document.getElementById('state-existing-plot');
    const stateCold = document.getElementById('state-cold-start');
    const stateDraft = document.getElementById('state-draft-editor');

    if (stateExisting) stateExisting.classList.add('hidden');
    if (stateCold) stateCold.classList.add('hidden');
    if (stateDraft) stateDraft.classList.add('hidden');

    if (stateName === 'existing' && stateExisting) stateExisting.classList.remove('hidden');
    else if (stateName === 'cold_start' && stateCold) stateCold.classList.remove('hidden');
    else if (stateName === 'draft_editor' && stateDraft) stateDraft.classList.remove('hidden');
  }

  // Render Existing Plot
  function renderExistingPlot(plot) {
    const promptEl = document.getElementById('plot-prompt');
    const catEl = document.getElementById('plot-category-badge');
    const fullLink = document.getElementById('link-open-full-atlas');
    const container = document.getElementById('choices-container');

    if (promptEl) promptEl.textContent = `"${plot.prompt}"`;
    if (catEl) catEl.textContent = (plot.category || 'DELIBERATION').replace(/_/g, ' ');
    if (fullLink) fullLink.href = `${config.backendUrl}/preview/index.html?qid=${encodeURIComponent(plot.question_id)}`;

    if (!container) return;
    container.innerHTML = '';

    const colors = ['#E66101', '#5D8AA8', '#008856', '#7B3294'];
    const symbols = ['●', '▲', '■', '◆'];

    (plot.choices || []).forEach((ch, idx) => {
      const ltr = ch.letter || ['A', 'B', 'C', 'D'][idx];
      const color = ch.color_hex || colors[idx % 4];
      const rawSymbol = ch.shape_symbol || symbols[idx % 4];
      const symbol = SYMBOL_MAP[rawSymbol] || rawSymbol;
      const label = ch.label || ch.text || '';
      const pct = ch.pct || (idx === 0 ? 46 : (idx === 1 ? 38 : (idx === 2 ? 11 : 5)));

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.id = `sidepanel-choice-${ltr}`;
      btn.className = 'choice-btn';
      btn.onclick = () => handleVote(ltr);

      btn.innerHTML = `
        <div class="choice-progress-fill" id="side-fill-${ltr}" style="background-color: ${color}; width: ${userVote ? pct + '%' : '0%'};"></div>
        <div class="choice-content">
          <span style="width: 22px; height: 22px; border-radius: 50%; background: ${color}; color: white; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; shrink-0; border: 1px solid #18181B;">
            ${symbol}
          </span>
          <span class="font-bold text-xs" style="color: var(--ink);">
            ${ltr}: <span class="font-normal text-gray-800">${escapeHtml(label)}</span>
          </span>
        </div>
        <span id="side-pct-${ltr}" class="choice-pct ${userVote ? '' : 'hidden'}" style="color: #374151;">
          ${pct}%
        </span>
      `;

      container.appendChild(btn);
    });

    if (userVote) {
      renderPostVoteDetails();
    }
  }

  // Handle Instant Vote
  async function handleVote(letter) {
    if (userVote) return;
    playClickSound(580);
    userVote = letter;
    activeStanceTab = letter;

    // Animate progress bars and reveal percentages
    (currentPlot.choices || []).forEach((ch) => {
      const ltr = ch.letter;
      const pct = ch.pct || (ltr === 'A' ? 46 : (ltr === 'B' ? 38 : (ltr === 'C' ? 11 : 5)));
      const fillEl = document.getElementById(`side-fill-${ltr}`);
      const pctEl = document.getElementById(`side-pct-${ltr}`);
      const btn = document.getElementById(`sidepanel-choice-${ltr}`);

      if (fillEl) fillEl.style.width = `${pct}%`;
      if (pctEl) pctEl.classList.remove('hidden');
      if (btn) {
        btn.disabled = true;
        if (ltr === letter) btn.classList.add('selected');
      }
    });

    renderPostVoteDetails();

    // Async record vote in backend
    try {
      await fetch(`${config.backendUrl}/api/vote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_id: currentPlot.question_id,
          choice_letter: letter,
          region_key: 'US_WEST',
          rater_salt: 'ext_voter_' + Math.random().toString(36).substring(2, 8),
          tier_level: 1
        })
      });
    } catch (e) {}
  }

  function renderPostVoteDetails() {
    const latchStrip = document.getElementById('voter-status-strip');
    const latchText = document.getElementById('voter-status-text');
    const regCard = document.getElementById('regional-strip-card');
    const nuanceCard = document.getElementById('nuance-card');

    if (latchStrip) latchStrip.classList.remove('hidden');
    if (latchText) latchText.textContent = `You Voted Option ${userVote} · Results Unlocked`;
    if (regCard) regCard.classList.remove('hidden');
    if (nuanceCard) nuanceCard.classList.remove('hidden');

    renderMiniRegionalStrip();
    renderStanceTabs();
    renderCurrentPerspective();
  }

  function renderMiniRegionalStrip() {
    const strip = document.getElementById('mini-regional-strip');
    if (!strip) return;
    const sampleRegions = [
      { code: 'US-W', opt: 'A', pct: '58%', color: '#E66101' },
      { code: 'EU-W', opt: 'A', pct: '61%', color: '#E66101' },
      { code: 'UK', opt: 'A', pct: '66%', color: '#E66101' },
      { code: 'US-E', opt: 'B', pct: '49%', color: '#5D8AA8' },
      { code: 'EA', opt: 'B', pct: '52%', color: '#5D8AA8' },
      { code: 'SA', opt: 'B', pct: '65%', color: '#5D8AA8' }
    ];

    strip.innerHTML = sampleRegions.map(r => `
      <div style="padding: 3px 6px; border-radius: 4px; background: white; border: 1px solid #D1D5DB; display: flex; flex-direction: column; align-items: center; min-width: 44px; shrink-0;">
        <span style="font-size: 8px; font-weight: bold; color: #6B7280;">${r.code}</span>
        <span style="font-size: 9px; font-weight: bold; color: ${r.color};">${r.opt} (${r.pct})</span>
      </div>
    `).join('');
  }

  // Load Stance Perspectives
  async function loadPerspectives(questionId) {
    try {
      const resp = await fetch(`${config.backendUrl}/api/perspectives/${encodeURIComponent(questionId)}/by_stance`);
      if (resp.ok) {
        const data = await resp.json();
        const baysData = (data.stance_dossier && data.stance_dossier.bays) ? data.stance_dossier.bays : (data.perspectives_by_stance || {});
        ['A', 'B', 'C', 'D'].forEach(letter => {
          const bay = baysData[letter];
          if (bay && Array.isArray(bay.perspectives) && bay.perspectives.length > 0) {
            cachedPerspectives[letter] = bay.perspectives;
          } else if (Array.isArray(bay) && bay.length > 0) {
            cachedPerspectives[letter] = bay;
          }
        });
      }
    } catch (e) {}

    // Fallback seed perspectives
    const defaults = {
      'A': [{
        perspective_id: 'p_ext_a',
        body: 'Individual autonomy and self-determination must form the core baseline of legitimate civic policy.',
        author_salt: '@local_citizen (Stockholm)',
        moral_lens: 'AUTONOMY',
        mutual_ratification_score: 0.88
      }],
      'B': [{
        perspective_id: 'p_ext_b',
        body: 'Collective welfare and community cohesion require bounded compromises on personal convenience.',
        author_salt: '@local_pragmatist (Berlin)',
        moral_lens: 'COMMUNAL_DUTY',
        mutual_ratification_score: 0.84
      }],
      'C': [{
        perspective_id: 'p_ext_c',
        body: 'Pragmatic thresholds and local opt-outs provide fair balance without rigid universal mandates.',
        author_salt: '@local_analyst (San Francisco)',
        moral_lens: 'CIVIC_RECIPROCITY',
        mutual_ratification_score: 0.76
      }],
      'D': [{
        perspective_id: 'p_ext_d',
        body: 'Preserving established cultural precedent and institutional continuity ensures societal stability.',
        author_salt: '@local_mentor (Tokyo)',
        moral_lens: 'INSTITUTIONAL_PRECEDENT',
        mutual_ratification_score: 0.72
      }]
    };

    ['A', 'B', 'C', 'D'].forEach(letter => {
      if (!cachedPerspectives[letter] || cachedPerspectives[letter].length === 0) {
        cachedPerspectives[letter] = defaults[letter];
      }
    });

    if (userVote) {
      renderStanceTabs();
      renderCurrentPerspective();
    }
  }

  function renderStanceTabs() {
    const container = document.getElementById('stance-tabs-strip');
    if (!container) return;
    container.innerHTML = '';

    ['A', 'B', 'C', 'D'].forEach(letter => {
      const isSelected = (activeStanceTab === letter);
      const isUserVote = (userVote === letter);
      const count = Array.isArray(cachedPerspectives[letter]) ? cachedPerspectives[letter].length : 0;

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `stance-tab-btn ${isSelected ? 'active' : ''}`;
      btn.onclick = () => {
        playClickSound(460);
        activeStanceTab = letter;
        renderStanceTabs();
        renderCurrentPerspective();
      };

      let label = `Bay ${letter} (${count})`;
      if (isUserVote) label += ' ★ You';
      else if (userVote) label += ' ⚡ Counter';
      btn.textContent = label;

      container.appendChild(btn);
    });
  }

  function renderCurrentPerspective() {
    const authorEl = document.getElementById('card-author');
    const lensEl = document.getElementById('card-moral-lens');
    const bodyEl = document.getElementById('card-body');
    const agreementEl = document.getElementById('card-agreement-pct');
    const calloutEl = document.getElementById('stance-callout-text');

    const items = Array.isArray(cachedPerspectives[activeStanceTab]) ? cachedPerspectives[activeStanceTab] : [];
    const item = items[0] || {
      perspective_id: `p_${activeStanceTab}_empty`,
      body: 'No recorded perspectives in this bay yet.',
      author_salt: '@local_citizen',
      moral_lens: 'AUTONOMY',
      mutual_ratification_score: 0.80
    };

    currentPerspectiveId = item.perspective_id;
    if (authorEl) authorEl.textContent = item.author_salt || '@local_citizen';
    if (lensEl) lensEl.textContent = `[${item.moral_lens || 'AUTONOMY'}]`;
    if (bodyEl) bodyEl.textContent = `"${item.body}"`;

    const approvalPct = Math.round((item.out_approval || item.mutual_ratification_score || 0.80) * 100);
    if (agreementEl) agreementEl.textContent = `🤝 ${approvalPct}% Agreement`;

    // Reset ratification buttons
    const btnSteelman = document.getElementById('btn-ratify-steelman');
    const btnTradeoff = document.getElementById('btn-ratify-tradeoff');
    if (btnSteelman) {
      btnSteelman.disabled = false;
      btnSteelman.textContent = '⚖️ Steelman';
    }
    if (btnTradeoff) {
      btnTradeoff.disabled = false;
      btnTradeoff.textContent = '✨ Tradeoff';
    }

    if (calloutEl) {
      if (userVote && activeStanceTab === userVote) {
        calloutEl.innerHTML = `Viewing takes from participants who shared your <strong>Stance ${userVote}</strong>.`;
      } else if (userVote) {
        calloutEl.innerHTML = `Viewing <strong>Stance ${activeStanceTab}</strong> counterweight arguments rated constructive by voters who disagree.`;
      }
    }
  }

  // 1-Tap Draft Generation Flow
  async function triggerDraftGeneration() {
    playClickSound(620);
    const ctaBtn = document.getElementById('btn-draft-plot-cta');
    if (ctaBtn) {
      ctaBtn.disabled = true;
      ctaBtn.textContent = '⚡ Formulating MECE Dilemma...';
    }

    try {
      const resp = await fetch(`${config.backendUrl}/api/plots/extract-draft`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: activeTabContext.canonical_url,
          title: activeTabContext.title,
          text_excerpt: activeTabContext.excerpt
        })
      });

      if (resp.ok) {
        const data = await resp.json();
        if (data && data.draft) {
          populateProofSheetDraft(data.draft);
          showState('draft_editor');
          return;
        }
      }
    } catch (err) {
      console.warn('[PLOT SidePanel] Draft extraction error:', err);
    } finally {
      if (ctaBtn) {
        ctaBtn.disabled = false;
        ctaBtn.textContent = '⚡ Draft Plot from this Page (1-Tap)';
      }
    }

    // Fallback manual template
    populateProofSheetDraft({
      title: activeTabContext.title || 'Discussion Dilemma',
      prompt: `Regarding '${(activeTabContext.title || 'this topic').slice(0, 70)}', which core principle takes precedence?`,
      choices: [
        { letter: 'A', label: 'Individual Sovereignty: Freedom of choice and private autonomy.' },
        { letter: 'B', label: 'Collective Harmony: Shared responsibility and public welfare.' },
        { letter: 'C', label: 'Pragmatic Balance: Contextual thresholds and flexible opt-outs.' },
        { letter: 'D', label: 'Established Precedent: Institutional stability and continuity.' }
      ],
      seed_rationale: 'Autonomy protects personal boundaries and authentic individual agency.',
      moral_lens: 'AUTONOMY',
      author_vote: 'A'
    });
    showState('draft_editor');
  }

  function populateProofSheetDraft(draft) {
    const titleInp = document.getElementById('draft-title');
    const promptInp = document.getElementById('draft-prompt');
    const choiceA = document.getElementById('draft-choice-a');
    const choiceB = document.getElementById('draft-choice-b');
    const choiceC = document.getElementById('draft-choice-c');
    const choiceD = document.getElementById('draft-choice-d');
    const lensSelect = document.getElementById('draft-moral-lens');
    const rationaleInp = document.getElementById('draft-rationale');

    if (titleInp) titleInp.value = draft.title || '';
    if (promptInp) promptInp.value = draft.prompt || '';
    if (draft.choices && draft.choices.length >= 4) {
      if (choiceA) choiceA.value = draft.choices[0].label || '';
      if (choiceB) choiceB.value = draft.choices[1].label || '';
      if (choiceC) choiceC.value = draft.choices[2].label || '';
      if (choiceD) choiceD.value = draft.choices[3].label || '';
    }
    if (lensSelect) lensSelect.value = draft.moral_lens || 'AUTONOMY';
    if (rationaleInp) rationaleInp.value = draft.seed_rationale || '';

    const radios = document.querySelectorAll('input[name="founder-vote"]');
    radios.forEach(r => {
      r.checked = (r.value === (draft.author_vote || 'A'));
    });
  }

  // Publish Custom Plot
  async function publishPlot() {
    playClickSound(680);
    const publishBtn = document.getElementById('btn-publish-plot');
    if (publishBtn) {
      publishBtn.disabled = true;
      publishBtn.textContent = '🚀 Publishing to Global Atlas...';
    }

    const title = document.getElementById('draft-title')?.value.trim() || 'Custom Dilemma';
    const prompt = document.getElementById('draft-prompt')?.value.trim() || 'Which principle takes priority?';
    const cA = document.getElementById('draft-choice-a')?.value.trim() || 'Option A';
    const cB = document.getElementById('draft-choice-b')?.value.trim() || 'Option B';
    const cC = document.getElementById('draft-choice-c')?.value.trim() || 'Option C';
    const cD = document.getElementById('draft-choice-d')?.value.trim() || 'Option D';
    const selectedVote = document.querySelector('input[name="founder-vote"]:checked')?.value || 'A';
    const moralLens = document.getElementById('draft-moral-lens')?.value || 'AUTONOMY';
    const rationale = document.getElementById('draft-rationale')?.value.trim() || 'Founding deliberative rationale.';

    const choices = [
      { letter: 'A', label: cA, shape_symbol: 'circle', color_hex: '#C85A17' },
      { letter: 'B', label: cB, shape_symbol: 'triangle', color_hex: '#003153' },
      { letter: 'C', label: cC, shape_symbol: 'square', color_hex: '#2E7D32' },
      { letter: 'D', label: cD, shape_symbol: 'diamond', color_hex: '#8E24AA' }
    ];

    try {
      const resp = await fetch(`${config.backendUrl}/api/plots/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title,
          prompt: prompt,
          category: 'COMMUNITY',
          choices: choices,
          canonical_url: activeTabContext.canonical_url,
          author_salt: '@founding_architect',
          author_vote: selectedVote,
          author_rationale: rationale,
          author_moral_lens: moralLens,
          author_macro_region: 'US_WEST'
        })
      });

      if (resp.ok) {
        const data = await resp.json();
        if (data && data.question) {
          currentPlot = data.question;
          userVote = selectedVote;
          renderExistingPlot(currentPlot);
          loadPerspectives(currentPlot.question_id);
          showState('existing');
          return;
        }
      }
    } catch (err) {
      console.warn('[PLOT SidePanel] Publish error:', err);
    } finally {
      if (publishBtn) {
        publishBtn.disabled = false;
        publishBtn.textContent = '🚀 Publish to Global Cultural Atlas';
      }
    }
  }

  // Ratify Perspective
  async function ratifyPerspective(evalType) {
    playClickSound(640);
    const btnSteelman = document.getElementById('btn-ratify-steelman');
    const btnTradeoff = document.getElementById('btn-ratify-tradeoff');
    const countEl = document.getElementById('card-agreement-pct');

    if (btnSteelman) btnSteelman.disabled = true;
    if (btnTradeoff) btnTradeoff.disabled = true;

    if (evalType === 'FAIR_STEELMAN' && btnSteelman) {
      btnSteelman.textContent = '✓ Steelman';
    } else if (btnTradeoff) {
      btnTradeoff.textContent = '✓ Tradeoff';
    }
    if (countEl) countEl.textContent = '🤝 Ratified by You';

    try {
      await fetch(`${config.backendUrl}/api/perspectives/rate_coherence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          perspective_id: currentPerspectiveId,
          rater_choice: userVote || 'A',
          eval_type: evalType
        })
      });
    } catch (e) {}
  }

  // Wire Event Listeners
  function initEvents() {
    // Settings
    document.getElementById('btn-toggle-settings')?.addEventListener('click', () => {
      const drawer = document.getElementById('settings-drawer');
      if (drawer) drawer.classList.toggle('hidden');
    });
    document.getElementById('btn-close-settings')?.addEventListener('click', () => {
      document.getElementById('settings-drawer')?.classList.add('hidden');
    });
    document.getElementById('setting-ai-mode')?.addEventListener('change', (e) => {
      const byok = document.getElementById('byok-container');
      if (byok) {
        if (e.target.value === 'byok') byok.classList.remove('hidden');
        else byok.classList.add('hidden');
      }
    });
    document.getElementById('btn-save-settings')?.addEventListener('click', async () => {
      config.backendUrl = document.getElementById('setting-backend-url')?.value.trim() || 'http://localhost:8000';
      config.aiMode = document.getElementById('setting-ai-mode')?.value || 'edge';
      config.byokKey = document.getElementById('setting-byok-key')?.value.trim() || '';
      await saveConfig();
      document.getElementById('settings-drawer')?.classList.add('hidden');
      checkBackendHealth();
      inspectCurrentPagePlot();
    });

    // Re-scan
    document.getElementById('btn-rescan-page')?.addEventListener('click', () => {
      playClickSound(500);
      detectActiveTab();
    });

    // 1-Tap Draft CTA
    document.getElementById('btn-draft-plot-cta')?.addEventListener('click', triggerDraftGeneration);

    // Cancel Draft
    document.getElementById('btn-cancel-draft')?.addEventListener('click', () => {
      showState('cold_start');
    });

    // Publish
    document.getElementById('btn-publish-plot')?.addEventListener('click', publishPlot);

    // Ratification
    document.getElementById('btn-ratify-steelman')?.addEventListener('click', () => ratifyPerspective('FAIR_STEELMAN'));
    document.getElementById('btn-ratify-tradeoff')?.addEventListener('click', () => ratifyPerspective('NUANCED_TRADEOFF'));

    // Chrome Runtime Message Listener for Tab Swapping
    if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.onMessage) {
      chrome.runtime.onMessage.addListener((msg) => {
        if (msg && msg.type === 'PLOT_TAB_CHANGED') {
          detectActiveTab();
        }
      });
    }

    // Expose controller methods for automated testing harness
    window.__PLOT_SIDEPANEL = {
      getConfig: () => config,
      setConfig: (c) => { config = { ...config, ...c }; },
      getActiveTab: () => activeTabContext,
      setActiveTab: (t) => {
        activeTabContext = { ...activeTabContext, ...t };
        updateContextInspectorUI();
        inspectCurrentPagePlot();
      },
      getCurrentPlot: () => currentPlot,
      triggerDraft: triggerDraftGeneration,
      publishPlot: publishPlot,
      vote: handleVote,
      ratify: ratifyPerspective,
      switchStance: (letter) => {
        activeStanceTab = letter;
        renderStanceTabs();
        renderCurrentPerspective();
      }
    };
  }

  // Initialization
  async function init() {
    await loadConfig();
    const urlInp = document.getElementById('setting-backend-url');
    const modeSelect = document.getElementById('setting-ai-mode');
    const keyInp = document.getElementById('setting-byok-key');
    if (urlInp) urlInp.value = config.backendUrl;
    if (modeSelect) modeSelect.value = config.aiMode;
    if (keyInp) keyInp.value = config.byokKey;

    initEvents();
    await checkBackendHealth();
    await detectActiveTab();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
