/* narRaters in-app tutorial framework.
 *
 * Exposes window.Tutorial with:
 *   Tutorial.installToggle(pageKey, { steps, iconRight })  -- adds the top-right
 *       (?) icon that toggles the tutorial on/off, and remembers per-page
 *       completion in localStorage so first-time users always see it.
 *   Tutorial.autoStart(pageKey, steps, { iconRight })       -- installs the
 *       toggle AND starts the tutorial right away if the user hasn't already
 *       completed it on this page.
 *   Tutorial.start(pageKey, steps)                          -- start at step 0.
 *   Tutorial.stop([markCompleted])                          -- close and (if
 *       true) persist a "completed" flag for this pageKey.
 *   Tutorial.next() / .prev()                               -- step navigation.
 *
 * Each step looks like:
 *   {
 *     target: 'css selector' | () => Element | null,   // null = centered card
 *     waitFor: 'css selector',                          // optional: wait until
 *                                                       // target exists/visible
 *     title: 'Short heading',
 *     body: 'HTML body text',
 *     placement: 'auto'|'top'|'bottom'|'left'|'right', // tooltip placement
 *     completeOn: {                                     // optional: advance
 *       event: 'click', target: 'css selector'          //   automatically on
 *     }                                                 //   user action
 *     hideNext: true,                                   // suppress "Next" btn
 *   }
 * When `completeOn` is present, the "Next" button is hidden so the user has to
 * perform the actual action (click the highlighted button, etc.) to advance —
 * which is the whole point of an interactive walkthrough.
 */
(function (window) {
    'use strict';

    var TUTORIAL_KEY_PREFIX = 'narraters-tutorial-completed:';
    var current = null;
    var completionTeardowns = [];
    var trackedTarget = null;
    var trackHandler = null;
    var waitObserver = null;

    function isCompleted(pageKey) {
        try { return localStorage.getItem(TUTORIAL_KEY_PREFIX + pageKey) === '1'; }
        catch (e) { return false; }
    }

    function setCompleted(pageKey, value) {
        try {
            if (value) localStorage.setItem(TUTORIAL_KEY_PREFIX + pageKey, '1');
            else localStorage.removeItem(TUTORIAL_KEY_PREFIX + pageKey);
        } catch (e) {}
    }

    function start(pageKey, steps) {
        if (!steps || !steps.length) return;
        stop(false);
        current = { pageKey: pageKey, steps: steps, index: 0 };
        ensureStyle();
        ensureOverlay();
        showStep(0);
        syncToggleButton();
    }

    function stop(markCompleted) {
        clearCompletionHandlers();
        if (waitObserver) { waitObserver.disconnect(); waitObserver = null; }
        if (trackHandler) {
            window.removeEventListener('resize', trackHandler);
            window.removeEventListener('scroll', trackHandler, true);
            trackHandler = null;
        }
        // Stop the post-render settle loop so it doesn't keep measuring the
        // (now-hidden) overlay or fight with the next step's positioning.
        if (_settleRaf) { cancelAnimationFrame(_settleRaf); _settleRaf = null; }
        if (_settleTimer) { clearTimeout(_settleTimer); _settleTimer = null; }
        trackedTarget = null;
        var overlay = document.getElementById('tutorial-overlay');
        if (overlay) overlay.classList.remove('active');
        if (markCompleted && current) setCompleted(current.pageKey, true);
        current = null;
        syncToggleButton();
    }

    function next() {
        if (!current) return;
        var i = current.index + 1;
        if (i >= current.steps.length) { stop(true); return; }
        current.index = i;
        showStep(i);
    }

    function prev() {
        if (!current || current.index === 0) return;
        current.index -= 1;
        showStep(current.index);
    }

    function ensureStyle() {
        if (document.getElementById('tutorial-styles')) return;
        var s = document.createElement('style');
        s.id = 'tutorial-styles';
        s.textContent =
            // The overlay container is **always** click-through. If it caught
            // clicks (pointer-events:auto) while a step was active, the user
            // could neither click the highlighted UI underneath (because the
            // overlay absorbed the click) nor close the tooltip in some browsers
            // (the click was intercepted by the parent overlay before reaching
            // the × button). Hit-testing is handled per-element below: the
            // tooltip explicitly enables pointer-events for its buttons; the
            // spotlight stays click-through so the highlighted UI works; an
            // optional .tutorial-backdrop only intercepts clicks for centered
            // intro cards (where there is no specific UI element to click).
            // Default-hidden so closing the tutorial actually makes everything
            // disappear. Previously the overlay had no display rule and only
            // .active toggled pointer-events, so the spotlight's giant box-shadow
            // dimming and the tooltip stayed visible after stop() — clicking ×
            // just left the page-dim and tooltip on screen with no way to escape.
            '#tutorial-overlay { position: fixed; inset: 0; pointer-events: none; z-index: 9000; display: none; }' +
            '#tutorial-overlay.active { display: block; }' +
            // border-radius is overwritten at runtime to match the highlighted
            // element's own computed border-radius, so the spotlight outline
            // wraps the element's actual shape (a tab\'s rounded corners, a pill button, etc.).
            '#tutorial-spotlight { position: fixed; box-shadow: 0 0 0 9999px rgba(0,0,0,0.55); border-radius: 6px;' +
            '    pointer-events: none; transition: top 0.2s ease, left 0.2s ease, width 0.2s ease, height 0.2s ease;' +
            '    outline: 3px solid #fbbf24; outline-offset: 2px; }' +
            '#tutorial-overlay.no-spotlight #tutorial-spotlight { display: none; }' +
            '#tutorial-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.55);' +
            '    pointer-events: none; display: none; }' +
            '#tutorial-overlay.no-spotlight #tutorial-backdrop { display: block; pointer-events: auto; }' +
            '#tutorial-tooltip { position: fixed; background: #1f2230; color: #f3f4f6;' +
            '    padding: 14px 16px 12px 16px; border-radius: 10px; max-width: 360px; min-width: 240px;' +
            '    box-shadow: 0 12px 32px rgba(0,0,0,0.5); border: 1px solid #fbbf24; font-size: 0.92em;' +
            '    line-height: 1.45; pointer-events: auto; transition: top 0.2s ease, left 0.2s ease; z-index: 9100; }' +
            '#tutorial-title { font-weight: 700; color: #fbbf24; margin-bottom: 6px; padding-right: 22px; font-size: 1.0em; }' +
            '#tutorial-body { margin-bottom: 10px; }' +
            '#tutorial-body code { background: rgba(255,255,255,0.08); padding: 1px 5px; border-radius: 4px; font-size: 0.92em; }' +
            '#tutorial-footer { display: flex; justify-content: space-between; align-items: center; gap: 8px; }' +
            '#tutorial-progress { color: #9ca3af; font-size: 0.82em; }' +
            '#tutorial-nav { display: flex; gap: 6px; }' +
            '#tutorial-prev, #tutorial-next { background: #fbbf24; color: #1f2230; border: none;' +
            '    padding: 5px 12px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.88em; }' +
            '#tutorial-prev { background: #4b5163; color: #f3f4f6; }' +
            '#tutorial-prev:hover { background: #5c6376; }' +
            '#tutorial-next:hover { background: #f59e0b; }' +
            '#tutorial-tooltip.no-next #tutorial-next { display: none; }' +
            '#tutorial-tooltip.no-prev #tutorial-prev { display: none; }' +
            '#tutorial-close { position: absolute; top: 4px; right: 6px; background: transparent;' +
            '    color: #9ca3af; border: none; font-size: 1.5em; cursor: pointer; line-height: 1; padding: 0 4px; }' +
            '#tutorial-close:hover { color: #f3f4f6; }' +
            // Tutorial toggle icon = circular button + "tutorial" caption stacked
            // beneath so its purpose is obvious without hovering.
            '.tutorial-toggle-icon { position: fixed; top: 20px; right: 70px; width: 38px; height: 38px;' +
            '    border-radius: 50%; background: rgba(0,0,0,0.5); color: #fbbf24;' +
            '    border: 1px solid rgba(251,191,36,0.35); display: flex; align-items: center;' +
            '    justify-content: center; font-size: 1.15em; font-weight: 700; cursor: pointer;' +
            '    z-index: 5000; transition: all 0.15s ease; user-select: none; }' +
            '.tutorial-toggle-icon:hover { background: rgba(0,0,0,0.75); border-color: #fbbf24; transform: scale(1.07); }' +
            '.tutorial-toggle-icon.active { background: #fbbf24; color: #1f2230; border-color: #f59e0b; }' +
            '.tutorial-toggle-icon[data-completed="1"]:not(.active) { opacity: 0.55; }' +
            '.tutorial-toggle-icon .tutorial-toggle-label { position: absolute; top: 100%; left: 50%;' +
            '    transform: translateX(-50%); margin-top: 4px; font-size: 0.65em; font-weight: 600;' +
            '    color: #fbbf24; letter-spacing: 0.05em; text-transform: uppercase;' +
            '    white-space: nowrap; pointer-events: none; opacity: 0.85; }' +
            '.tutorial-toggle-icon.active .tutorial-toggle-label { color: #1f2230; }';
        document.head.appendChild(s);
    }

    function ensureOverlay() {
        if (document.getElementById('tutorial-overlay')) return;
        var overlay = document.createElement('div');
        overlay.id = 'tutorial-overlay';
        overlay.innerHTML =
            '<div id="tutorial-backdrop"></div>' +
            '<div id="tutorial-spotlight"></div>' +
            '<div id="tutorial-tooltip">' +
            '  <button id="tutorial-close" type="button" title="Close tutorial">&times;</button>' +
            '  <div id="tutorial-title"></div>' +
            '  <div id="tutorial-body"></div>' +
            '  <div id="tutorial-footer">' +
            '    <span id="tutorial-progress"></span>' +
            '    <div id="tutorial-nav">' +
            '      <button id="tutorial-prev" type="button">← Back</button>' +
            '      <button id="tutorial-next" type="button">Next →</button>' +
            '    </div>' +
            '  </div>' +
            '</div>';
        document.body.appendChild(overlay);

        // Click + mousedown + touchstart, all with capture+stopPropagation, so
        // these buttons can't be silently swallowed by the page's own
        // document-level mousedown handlers (e.g. the matrix outside-click
        // closer on subject.html, or any per-page click capture wired to the
        // body). pointerdown covers stylus/pen too.
        var bindBtn = function (id, fn) {
            var btn = document.getElementById(id);
            if (!btn) return;
            ['pointerdown', 'mousedown', 'click', 'touchstart'].forEach(function (evt) {
                btn.addEventListener(evt, function (e) {
                    e.stopPropagation();
                    if (evt === 'click') { e.preventDefault(); fn(); }
                }, true);
            });
        };
        bindBtn('tutorial-close', function () { stop(true); });
        bindBtn('tutorial-next', function () { next(); });
        bindBtn('tutorial-prev', function () { prev(); });
    }

    function showStep(i) {
        if (!current) return;
        var step = current.steps[i];
        if (!step) { stop(true); return; }

        if (waitObserver) { waitObserver.disconnect(); waitObserver = null; }

        // If the target / waitFor element isn't on the page yet, set up a
        // MutationObserver and try again as soon as it appears. This is how we
        // tutorial-walk a button that lives inside a modal that the user hasn't
        // opened yet, or an icon that only appears after a step completes.
        var waitSel = step.waitFor || (typeof step.target === 'string' ? step.target : null);
        if (waitSel && !document.querySelector(waitSel)) {
            waitObserver = new MutationObserver(function () {
                if (document.querySelector(waitSel)) {
                    waitObserver.disconnect();
                    waitObserver = null;
                    showStep(i);
                }
            });
            waitObserver.observe(document.body, { childList: true, subtree: true });
            renderWaiting(step);
            return;
        }

        var target = null;
        if (typeof step.target === 'function') target = step.target();
        else if (typeof step.target === 'string') target = document.querySelector(step.target);

        renderStep(step, target, i);
        setupCompletion(step);
        trackTarget(step, target);
    }

    function renderWaiting(step) {
        var overlay = document.getElementById('tutorial-overlay');
        overlay.classList.add('active');
        overlay.classList.add('no-spotlight');
        var tooltip = document.getElementById('tutorial-tooltip');
        document.getElementById('tutorial-title').textContent = step.title || 'Waiting…';
        document.getElementById('tutorial-body').innerHTML = (step.waitingBody || step.body || 'Waiting for the next element to appear…');
        document.getElementById('tutorial-progress').textContent =
            'Step ' + (current.index + 1) + ' of ' + current.steps.length;
        tooltip.classList.add('no-next');
        tooltip.classList.toggle('no-prev', current.index === 0);
        tooltip.style.left = '50%';
        tooltip.style.top = '50%';
        tooltip.style.transform = 'translate(-50%, -50%)';
    }

    function renderStep(step, target, i) {
        var overlay = document.getElementById('tutorial-overlay');
        overlay.classList.add('active');

        var tooltip = document.getElementById('tutorial-tooltip');
        tooltip.style.transform = '';
        document.getElementById('tutorial-title').textContent = step.title || '';
        document.getElementById('tutorial-body').innerHTML = step.body || '';
        document.getElementById('tutorial-progress').textContent =
            'Step ' + (i + 1) + ' of ' + current.steps.length;

        var hideNext = !!(step.completeOn || step.hideNext);
        tooltip.classList.toggle('no-next', hideNext);
        tooltip.classList.toggle('no-prev', i === 0);

        if (target) {
            overlay.classList.remove('no-spotlight');
            positionSpotlight(target);
            // Position tooltip after spotlight so the tooltip can measure itself.
            requestAnimationFrame(function () {
                positionTooltip(tooltip, target.getBoundingClientRect(), step.placement || 'auto');
            });
            // The first measurement can land mid-animation — the method modal,
            // for example, scales from 0→1 over 300ms via CSS keyframes, so a
            // spotlight measured at frame 1 would be locked to the half-scaled
            // rectangle. Re-measure across the next ~700ms so the spotlight
            // catches up to the element\'s final position once any open / scale /
            // fade transition has settled. Also handles modals whose layout
            // shifts after their content streams in (e.g. method-options-container
            // populating after the modal is already visible).
            settleSpotlight(target, step.placement || 'auto');
        } else {
            overlay.classList.add('no-spotlight');
            tooltip.style.left = '50%';
            tooltip.style.top = '50%';
            tooltip.style.transform = 'translate(-50%, -50%)';
        }
    }

    var _settleTimer = null;
    var _settleRaf = null;
    function settleSpotlight(target, placement) {
        if (_settleTimer) { clearTimeout(_settleTimer); _settleTimer = null; }
        if (_settleRaf) { cancelAnimationFrame(_settleRaf); _settleRaf = null; }
        var deadline = performance.now() + 700;
        var lastKey = '';
        function tick() {
            _settleRaf = null;
            if (!current || !target || !document.body.contains(target)) return;
            var rect = target.getBoundingClientRect();
            // Skip zero-sized rects (target still display:none or mid-animation
            // at scale(0)) — let the next frame try again.
            if (rect.width > 0 && rect.height > 0) {
                var key = [rect.left, rect.top, rect.width, rect.height].join(',');
                if (key !== lastKey) {
                    lastKey = key;
                    positionSpotlight(target);
                    var tooltip = document.getElementById('tutorial-tooltip');
                    if (tooltip) positionTooltip(tooltip, rect, placement);
                }
            }
            if (performance.now() < deadline) {
                _settleRaf = requestAnimationFrame(tick);
            } else {
                _settleTimer = null;
            }
        }
        _settleRaf = requestAnimationFrame(tick);
    }

    function positionSpotlight(target) {
        var spotlight = document.getElementById('tutorial-spotlight');
        var rect = target.getBoundingClientRect();
        // Tight padding so the spotlight hugs the element's actual shape
        // rather than swallowing surrounding whitespace.
        var pad = 3;
        spotlight.style.left = (rect.left - pad) + 'px';
        spotlight.style.top = (rect.top - pad) + 'px';
        spotlight.style.width = (rect.width + pad * 2) + 'px';
        spotlight.style.height = (rect.height + pad * 2) + 'px';
        // Match the target's own border-radius (a button, tab, badge, etc.
        // becomes a rounded-rectangle highlight; a square cell stays square).
        var br = '';
        try {
            var cs = window.getComputedStyle(target);
            br = cs && cs.borderRadius ? cs.borderRadius : '';
        } catch (e) {}
        spotlight.style.borderRadius = br || '6px';
    }

    function positionTooltip(tooltip, rect, placement) {
        var tt = tooltip.getBoundingClientRect();
        var pageW = window.innerWidth;
        var pageH = window.innerHeight;
        var margin = 16;
        if (placement === 'auto') {
            var spaceRight = pageW - rect.right - margin;
            var spaceLeft = rect.left - margin;
            var spaceBelow = pageH - rect.bottom - margin;
            if (spaceRight >= tt.width + 16) placement = 'right';
            else if (spaceLeft >= tt.width + 16) placement = 'left';
            else if (spaceBelow >= tt.height + 16) placement = 'bottom';
            else placement = 'top';
        }
        var top, left;
        if (placement === 'right') {
            left = rect.right + margin;
            top = rect.top + rect.height / 2 - tt.height / 2;
        } else if (placement === 'left') {
            left = rect.left - margin - tt.width;
            top = rect.top + rect.height / 2 - tt.height / 2;
        } else if (placement === 'bottom') {
            left = rect.left + rect.width / 2 - tt.width / 2;
            top = rect.bottom + margin;
        } else {
            left = rect.left + rect.width / 2 - tt.width / 2;
            top = rect.top - margin - tt.height;
        }
        if (left < 8) left = 8;
        if (left + tt.width > pageW - 8) left = pageW - 8 - tt.width;
        if (top < 8) top = 8;
        if (top + tt.height > pageH - 8) top = pageH - 8 - tt.height;
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    }

    function setupCompletion(step) {
        clearCompletionHandlers();
        if (!step.completeOn) return;
        if (step.completeOn.event === 'click') {
            var sel = step.completeOn.target;
            // Walk e.target's ancestor chain looking for the matching selector.
            // If e.target itself is the overlay or one of its children (which
            // shouldn't happen now that the overlay is pointer-events:none, but
            // we keep this defensive in case a future page injects something on
            // top), fall back to elementsFromPoint() at the click coordinates
            // to see what was *really* clicked through the overlay.
            var checkElement = function (el) {
                while (el && el !== document.body) {
                    if (el.matches && el.matches(sel)) return true;
                    el = el.parentElement;
                }
                return false;
            };
            var handler = function (e) {
                var t = e.target;
                if (t && t.closest && t.closest('#tutorial-overlay, .tutorial-toggle-icon')) {
                    // Click landed on our own UI — never count it as completion.
                    return;
                }
                var matched = checkElement(t);
                if (!matched && typeof document.elementsFromPoint === 'function') {
                    var stack = document.elementsFromPoint(e.clientX, e.clientY) || [];
                    for (var i = 0; i < stack.length; i++) {
                        var el = stack[i];
                        if (el && el.closest && el.closest('#tutorial-overlay, .tutorial-toggle-icon')) continue;
                        if (checkElement(el)) { matched = true; break; }
                    }
                }
                if (matched) {
                    // Let the real click handler (executeStep, openModal, etc.)
                    // run synchronously first, then advance one tick later.
                    setTimeout(function () { next(); }, 60);
                }
            };
            document.addEventListener('click', handler, true);
            completionTeardowns.push(function () { document.removeEventListener('click', handler, true); });
        } else if (step.completeOn.event === 'custom' && typeof step.completeOn.subscribe === 'function') {
            var unsub = step.completeOn.subscribe(function () { next(); });
            if (typeof unsub === 'function') completionTeardowns.push(unsub);
        }
    }

    function clearCompletionHandlers() {
        completionTeardowns.forEach(function (fn) { try { fn(); } catch (e) {} });
        completionTeardowns = [];
    }

    function trackTarget(step, target) {
        if (trackHandler) {
            window.removeEventListener('resize', trackHandler);
            window.removeEventListener('scroll', trackHandler, true);
            trackHandler = null;
        }
        trackedTarget = target || null;
        if (!target) return;
        trackHandler = function () {
            if (!current || !trackedTarget) return;
            if (!document.body.contains(trackedTarget)) return;
            positionSpotlight(trackedTarget);
            positionTooltip(document.getElementById('tutorial-tooltip'),
                trackedTarget.getBoundingClientRect(), step.placement || 'auto');
        };
        window.addEventListener('resize', trackHandler);
        window.addEventListener('scroll', trackHandler, true);
    }

    function syncToggleButton() {
        var btn = document.querySelector('.tutorial-toggle-icon');
        if (!btn) return;
        btn.classList.toggle('active', !!current);
        if (current) btn.setAttribute('data-completed', '0');
        else btn.setAttribute('data-completed', isCompleted(btn.getAttribute('data-tutorial-key')) ? '1' : '0');
    }

    function installToggle(pageKey, opts) {
        opts = opts || {};
        // Reuse an existing icon (e.g. one hardcoded into the page so it's
        // visible on first paint, before any data-fetch finishes). If none
        // exists, create one. Either way the click handler and pageKey are
        // refreshed for the current call site so per-tab walks stay correct.
        var btn = document.querySelector('.tutorial-toggle-icon');
        if (!btn) {
            btn = document.createElement('div');
            btn.className = 'tutorial-toggle-icon';
            btn.innerHTML = '?<span class="tutorial-toggle-label">tutorial</span>';
            document.body.appendChild(btn);
        } else if (!btn.querySelector('.tutorial-toggle-label')) {
            // Adopt a bare icon that's missing the label.
            btn.innerHTML = '?<span class="tutorial-toggle-label">tutorial</span>';
        }
        btn.title = 'Page tutorial — click to toggle on/off';
        btn.setAttribute('data-tutorial-key', pageKey);
        if (opts.right) btn.style.right = opts.right;
        // Replace any previously-bound click handler so the new pageKey/steps
        // close over the latest values.
        if (btn._tutorialClickHandler) {
            btn.removeEventListener('click', btn._tutorialClickHandler);
        }
        btn._tutorialClickHandler = function () {
            if (current) {
                stop(false);
            } else {
                setCompleted(pageKey, false);
                var stepsForRun = opts.steps;
                if (typeof opts.stepsFactory === 'function') stepsForRun = opts.stepsFactory();
                start(pageKey, stepsForRun || []);
            }
        };
        btn.addEventListener('click', btn._tutorialClickHandler);
        syncToggleButton();
    }

    function autoStart(pageKey, steps, opts) {
        opts = opts || {};
        ensureStyle();
        installToggle(pageKey, { steps: steps, right: opts.iconRight || '70px' });
        if (!isCompleted(pageKey)) {
            // Defer one frame so the rest of page-init can settle.
            requestAnimationFrame(function () { start(pageKey, steps); });
        }
    }

    window.Tutorial = {
        start: start,
        stop: stop,
        next: next,
        prev: prev,
        installToggle: installToggle,
        autoStart: autoStart,
        isCompleted: isCompleted,
        setCompleted: setCompleted,
        reset: function (key) { setCompleted(key, false); }
    };

    // Auto-adopt any pre-rendered .tutorial-toggle-icon as soon as the DOM is
    // ready — this guarantees the icon is clickable from first paint (rather
    // than waiting for the page's data-fetch and per-tab setup to run). When
    // the page-specific setup later calls installToggle() with the *real*
    // steps for the active tab/page, that call replaces this placeholder
    // handler and the click then starts the actual walkthrough.
    function adoptPrerenderedIcons() {
        ensureStyle();
        var icons = document.querySelectorAll('.tutorial-toggle-icon');
        icons.forEach(function (btn) {
            if (btn._tutorialClickHandler) return; // already wired
            // Ensure the label span exists.
            if (!btn.querySelector('.tutorial-toggle-label')) {
                btn.innerHTML = '?<span class="tutorial-toggle-label">tutorial</span>';
            }
            var pageKey = btn.getAttribute('data-tutorial-key') || 'page';
            btn._tutorialClickHandler = function () {
                if (current) { stop(false); return; }
                // No real steps yet — once the page-specific setup runs it
                // will replace this handler. Until then, no-op gracefully so
                // the click at least registers without throwing.
                setCompleted(pageKey, false);
                syncToggleButton();
            };
            btn.addEventListener('click', btn._tutorialClickHandler);
        });
        syncToggleButton();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', adoptPrerenderedIcons);
    } else {
        adoptPrerenderedIcons();
    }
})(window);
