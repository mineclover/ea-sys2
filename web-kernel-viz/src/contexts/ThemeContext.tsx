
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';

type Mode = 'light' | 'dark';
type Base = 'slate';
type Accent = 'blue';

/** Legacy compat alias */
export type Theme = Mode;

interface ThemeConfig {
    mode: Mode;
    base: Base;
    accent: Accent;
}

interface ThemeContextValue {
    /** Current mode (light/dark) */
    theme: Mode;
    toggleTheme: () => void;
    /** Full 3-axis config */
    config: ThemeConfig;
    setConfig: (patch: Partial<ThemeConfig>) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = 'ea-sys-theme-config';
const LEGACY_KEY = 'ea-sys-theme';

function getInitialConfig(): ThemeConfig {
    // Try new config first
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            const parsed = JSON.parse(stored);
            if (parsed.mode === 'light' || parsed.mode === 'dark') {
                return { mode: parsed.mode, base: 'slate', accent: 'blue' };
            }
        }
    } catch { /* ignore */ }

    // Fall back to legacy key
    const legacy = localStorage.getItem(LEGACY_KEY);
    if (legacy === 'light' || legacy === 'dark') {
        return { mode: legacy, base: 'slate', accent: 'blue' };
    }

    // System preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    return { mode: prefersDark ? 'dark' : 'light', base: 'slate', accent: 'blue' };
}

export function ThemeProvider({ children }: { children: ReactNode }) {
    const [config, setConfigState] = useState<ThemeConfig>(getInitialConfig);

    useEffect(() => {
        const root = document.documentElement;

        // Mode
        if (config.mode === 'dark') {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }

        // Base & accent data attributes (for future CSS selector expansion)
        root.dataset.base = config.base;
        root.dataset.accent = config.accent;

        // Persist
        localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
        // Keep legacy key in sync for any old code
        localStorage.setItem(LEGACY_KEY, config.mode);
    }, [config]);

    const toggleTheme = useCallback(() => {
        setConfigState((prev) => ({ ...prev, mode: prev.mode === 'light' ? 'dark' : 'light' }));
    }, []);

    const setConfig = useCallback((patch: Partial<ThemeConfig>) => {
        setConfigState((prev) => ({ ...prev, ...patch }));
    }, []);

    return (
        <ThemeContext.Provider value={{ theme: config.mode, toggleTheme, config, setConfig }}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    const ctx = useContext(ThemeContext);
    if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
    return ctx;
}
