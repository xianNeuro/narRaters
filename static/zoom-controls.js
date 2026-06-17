/**
 * Page zoom controls — two magnifying-glass buttons fixed at the top-right
 * corner (stacked under the settings gear) that zoom the page in/out, doing
 * what the browser's Cmd/Ctrl + and Cmd/Ctrl - shortcuts do.
 *
 * Real browser zoom cannot be driven from JavaScript, so the buttons emulate
 * it with the same mechanism the pages already use for their default scale:
 * the CSS `zoom` property on <html> (0.8 on the inspection page, 0.9 on the
 * dashboard/pipeline pages, set in each page's stylesheet). The buttons
 * multiply that per-page base zoom by a user factor stepped through the same
 * zoom ladder desktop browsers use, write the product to the inline style,
 * and keep the factor in localStorage (per page) so it survives reloads.
 * After every change a synthetic window `resize` is dispatched so pages that
 * size panels from the viewport (the inspection page) refit themselves.
 */
(function () {
    'use strict';

    // Chrome's zoom levels, used as multipliers on the page's own base zoom;
    // 1 = the page's normal size.
    var LEVELS = [0.33, 0.5, 0.67, 0.75, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3];

    var storageKey = 'narraters-zoom:' + (location.pathname.split('/')[1] || 'dashboard');
    var baseZoom = 1;
    var factor = 1;

    function loadFactor() {
        try {
            var v = parseFloat(localStorage.getItem(storageKey));
            if (isFinite(v) && v >= LEVELS[0] && v <= LEVELS[LEVELS.length - 1]) return v;
        } catch (e) {}
        return 1;
    }

    function saveFactor() {
        try {
            if (factor === 1) localStorage.removeItem(storageKey);
            else localStorage.setItem(storageKey, String(factor));
        } catch (e) {}
    }

    // The page's stylesheet zoom, measured with the inline override cleared.
    // An in-flow probe is used instead of reading the computed `zoom` value
    // because ancestor zoom reliably scales in-flow boxes in every browser,
    // while computed-style support for `zoom` varies.
    function measureBaseZoom() {
        var inline = document.documentElement.style.zoom;
        document.documentElement.style.zoom = '';
        var probe = document.createElement('div');
        probe.style.cssText = 'position:absolute;left:-99999px;top:0;width:1000px;height:10px;' +
            'margin:0;padding:0;border:0;visibility:hidden;pointer-events:none;';
        document.body.appendChild(probe);
        var z = probe.getBoundingClientRect().width / 1000;
        probe.remove();
        document.documentElement.style.zoom = inline;
        return (isFinite(z) && z > 0) ? z : 1;
    }

    function applyZoom() {
        document.documentElement.style.zoom = factor === 1 ? '' : String(baseZoom * factor);
        updateButtons();
        // Let viewport-sized layouts (inspection panels, causal lines) refit.
        window.dispatchEvent(new Event('resize'));
    }

    function step(direction) {
        // Snap to the nearest ladder entry, then move one level.
        var idx = 0, best = Infinity;
        for (var i = 0; i < LEVELS.length; i++) {
            var d = Math.abs(LEVELS[i] - factor);
            if (d < best) { best = d; idx = i; }
        }
        idx = Math.max(0, Math.min(LEVELS.length - 1, idx + direction));
        factor = LEVELS[idx];
        saveFactor();
        applyZoom();
    }

    var inBtn = null, outBtn = null;

    function updateButtons() {
        if (!inBtn) return;
        var pct = Math.round(factor * 100) + '%';
        inBtn.disabled = factor >= LEVELS[LEVELS.length - 1];
        outBtn.disabled = factor <= LEVELS[0];
        inBtn.title = 'Zoom in (like ⌘ +) — now ' + pct;
        outBtn.title = 'Zoom out (like ⌘ −) — now ' + pct;
    }

    function magnifierSvg(sign) {
        return '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
            ' stroke-width="2" stroke-linecap="round" aria-hidden="true">' +
            '<circle cx="10" cy="10" r="7"></circle>' +
            '<line x1="15.2" y1="15.2" x2="21" y2="21"></line>' +
            (sign === '+' ? '<line x1="10" y1="7" x2="10" y2="13"></line>' : '') +
            '<line x1="7" y1="10" x2="13" y2="10"></line>' +
            '</svg>';
    }

    function makeButton(sign, label) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'page-zoom-btn';
        btn.setAttribute('aria-label', label);
        btn.innerHTML = magnifierSvg(sign);
        btn.addEventListener('click', function () { step(sign === '+' ? 1 : -1); });
        return btn;
    }

    function init() {
        baseZoom = measureBaseZoom();
        factor = loadFactor();

        var style = document.createElement('style');
        style.textContent =
            // Mirrors .settings-icon (the fixed gear above this stack) so the
            // column of top-right controls reads as one set.
            '.page-zoom-controls { position: fixed; top: 70px; right: 20px; display: flex;' +
            ' flex-direction: column; gap: 8px; z-index: 999; }' +
            '.page-zoom-btn { width: 40px; height: 40px; background: var(--bg2, #fff);' +
            ' border: 1px solid var(--bdr, #ccc); border-radius: 50%; display: flex;' +
            ' align-items: center; justify-content: center; cursor: pointer;' +
            ' color: var(--t1, #444); padding: 0; transition: all var(--tr, 0.2s);' +
            ' box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2); }' +
            '.page-zoom-btn:hover:not(:disabled) { background: var(--bg3, #eee);' +
            ' border-color: var(--acc, #6c63ff); color: var(--acc, #6c63ff); }' +
            '.page-zoom-btn:disabled { opacity: 0.4; cursor: default; }';
        document.head.appendChild(style);

        var wrap = document.createElement('div');
        wrap.className = 'page-zoom-controls';
        inBtn = makeButton('+', 'Zoom in');
        outBtn = makeButton('-', 'Zoom out');
        wrap.appendChild(inBtn);
        wrap.appendChild(outBtn);
        document.body.appendChild(wrap);

        // Small public API so other UI (e.g. the benchmark rater view's own
        // "Smaller"/"Bigger" buttons) can drive the same zoom ladder.
        window.PageZoom = { in: function () { step(1); }, out: function () { step(-1); } };

        if (factor !== 1) applyZoom();
        else updateButtons();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
