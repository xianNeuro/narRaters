// Theme Manager - Handles dark/day mode switching across all pages
(function() {
    'use strict';
    
    const THEME_STORAGE_KEY = 'narrative-processor-theme';
    const THEMES = {
        DARK: 'dark',
        DAY: 'day'
    };
    
    // Dark mode colors (default)
    const darkColors = {
        '--bg0': '#0b0d14',
        '--bg1': '#111527',
        '--bg2': '#1a1f36',
        '--bg3': '#242b4a',
        '--t0': '#f0f2f5',
        '--t1': '#c4c9db',
        '--t2': '#8890a8',
        '--t3': '#5c6380',
        '--bdr': '#2a3050',
        '--bdr2': '#353c60',
        '--acc': '#6c63ff',
        '--acc2': '#8b84ff',
        '--accbg': 'rgba(108, 99, 255, 0.12)',
        '--red': '#ef4444',
        '--grn': '#22c55e',
        '--ylw': '#f59e0b',
        '--shadow': '0 20px 60px rgba(0, 0, 0, 0.4)',
        '--shadow-sm': '0 2px 8px rgba(0, 0, 0, 0.2)',
        '--shadow-modal': '0 20px 60px rgba(0, 0, 0, 0.5)',
        '--overlay': 'rgba(0, 0, 0, 0.5)',
    };
    
    // Day mode (Light) - white page background, half-transparent grey boxes, bright UI with dark fonts
    const dayColors = {
        '--bg0': '#ffffff',
        '--bg1': 'rgba(0, 0, 0, 0.04)',
        '--bg2': 'rgba(0, 0, 0, 0.08)',
        '--bg3': 'rgba(0, 0, 0, 0.12)',
        '--t0': '#0d0d0d',
        '--t1': '#1a1a1a',
        '--t2': '#333333',
        '--t3': '#525252',
        '--bdr': 'rgba(0, 0, 0, 0.12)',
        '--bdr2': 'rgba(0, 0, 0, 0.18)',
        '--acc': '#6c63ff',
        '--acc2': '#8b84ff',
        '--accbg': 'rgba(108, 99, 255, 0.12)',
        '--red': '#ef4444',
        '--grn': '#22c55e',
        '--ylw': '#f59e0b',
        '--shadow': '0 4px 20px rgba(0, 0, 0, 0.08)',
        '--shadow-sm': '0 2px 8px rgba(0, 0, 0, 0.08)',
        '--shadow-modal': '0 20px 50px rgba(0, 0, 0, 0.12)',
        '--overlay': 'rgba(0, 0, 0, 0.25)',
    };
    
    // Get current theme from localStorage or default to dark
    function getCurrentTheme() {
        const stored = localStorage.getItem(THEME_STORAGE_KEY);
        return stored === THEMES.DAY ? THEMES.DAY : THEMES.DARK;
    }
    
    // Apply theme colors to CSS variables
    function applyTheme(theme) {
        const colors = theme === THEMES.DAY ? dayColors : darkColors;
        const root = document.documentElement;
        
        // Mark root so override selector wins over template :root
        root.setAttribute('data-theme', theme);
        
        // Remove old theme override if it exists
        let oldStyle = document.getElementById('theme-override');
        if (oldStyle) {
            oldStyle.remove();
        }
        
        // Create new style tag - use html[data-theme="..."] so we beat template :root
        let style = document.createElement('style');
        style.id = 'theme-override';
        style.setAttribute('data-theme', theme);
        
        let selector = 'html[data-theme="' + theme + '"]';
        let css = selector + ' { ';
        Object.keys(colors).forEach(key => {
            css += key + ': ' + colors[key] + ' !important; ';
        });
        css += '}';
        style.textContent = css;
        
        document.head.appendChild(style);
        
        // Inline on root as backup so it works even before style is parsed
        Object.keys(colors).forEach(key => {
            root.style.setProperty(key, colors[key]);
        });
        
        localStorage.setItem(THEME_STORAGE_KEY, theme);
        updateSettingsModal(theme);
    }
    
    // Initialize theme on page load
    function initTheme() {
        const theme = getCurrentTheme();
        applyTheme(theme);
    }
    
    // Switch theme
    function switchTheme(theme) {
        if (theme !== THEMES.DARK && theme !== THEMES.DAY) {
            console.error('Invalid theme:', theme);
            return;
        }
        applyTheme(theme);
    }
    
    // Update settings modal UI
    function updateSettingsModal(currentTheme) {
        const darkRadio = document.getElementById('theme-dark');
        const dayRadio = document.getElementById('theme-day');
        
        if (darkRadio) darkRadio.checked = (currentTheme === THEMES.DARK);
        if (dayRadio) dayRadio.checked = (currentTheme === THEMES.DAY);
    }
    
    // Apply theme immediately so first paint uses saved preference (avoids flash of wrong theme)
    (function applyThemeSync() {
        const theme = localStorage.getItem(THEME_STORAGE_KEY) === THEMES.DAY ? THEMES.DAY : THEMES.DARK;
        const colors = theme === THEMES.DAY ? dayColors : darkColors;
        const root = document.documentElement;
        root.setAttribute('data-theme', theme);
        Object.keys(colors).forEach(function(key) {
            root.style.setProperty(key, colors[key]);
        });
    })();

    // Full init on DOM ready (style tag + settings modal sync)
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTheme);
    } else {
        initTheme();
    }
    
    // Export functions to global scope
    window.ThemeManager = {
        switchTheme: switchTheme,
        getCurrentTheme: getCurrentTheme,
        THEMES: THEMES
    };
})();

