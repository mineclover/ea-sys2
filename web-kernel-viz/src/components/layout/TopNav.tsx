
import { useState, useCallback, useEffect, useRef } from 'react';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { useTheme } from '@/contexts/ThemeContext';

export type Section = 'explorer' | 'needs' | 'governance' | 'status' | 'schema' | 'admin';

export type ExplorerView = 'kernel-schema' | 'profile-graph' | 'rules' | 'dev-topology';
export type NeedsView = 'catalog';
export type GovernanceView = 'rule-lifecycle' | 'models' | 'decisions' | 'simulation' | 'business-flow' | 'impact';
export type StatusView = 'entities' | 'relations' | 'rules' | 'layers' | 'frameworks' | 'kernel';
export type SchemaView = 'infra' | 'decision' | 'needs' | 'kernel' | 'flow' | 'governance';
export type AdminView = 'business' | 'i18n' | 'self-model';
export type SubView = ExplorerView | NeedsView | GovernanceView | StatusView | SchemaView | AdminView;

const SECTIONS: { key: Section; label: string; defaultSub: SubView }[] = [
    { key: 'explorer', label: 'Explorer', defaultSub: 'kernel-schema' },
    { key: 'needs', label: 'Needs', defaultSub: 'catalog' },
    { key: 'governance', label: 'Governance', defaultSub: 'rule-lifecycle' },
    { key: 'schema', label: 'Schema', defaultSub: 'kernel' },
    { key: 'status', label: 'Status', defaultSub: 'entities' },
    { key: 'admin', label: 'Admin', defaultSub: 'business' },
];

const EXPLORER_VIEWS: { key: ExplorerView; label: string }[] = [
    { key: 'kernel-schema', label: 'Kernel Schema' },
    { key: 'profile-graph', label: 'Profile Graph' },
    { key: 'rules', label: 'Rules' },
    { key: 'dev-topology', label: 'Dev Topology' },
];

const NEEDS_VIEWS: { key: NeedsView; label: string }[] = [
    { key: 'catalog', label: 'Needs Catalog' },
];

const GOVERNANCE_VIEWS: { key: GovernanceView; label: string }[] = [
    { key: 'rule-lifecycle', label: 'Rule Lifecycle' },
    { key: 'models', label: 'Models' },
    { key: 'decisions', label: 'Decisions' },
    { key: 'simulation', label: 'Simulation' },
    { key: 'business-flow', label: 'Business Flow' },
    { key: 'impact', label: 'Impact Analysis' },
];

const STATUS_VIEWS: { key: StatusView; label: string }[] = [
    { key: 'entities', label: 'Entities' },
    { key: 'relations', label: 'Relations' },
    { key: 'rules', label: 'Rules' },
    { key: 'layers', label: 'Layers' },
    { key: 'frameworks', label: 'Frameworks' },
    { key: 'kernel', label: 'Kernel Schema' },
];

const SCHEMA_VIEWS: { key: SchemaView; label: string }[] = [
    { key: 'infra', label: 'Infra' },
    { key: 'decision', label: 'Decision' },
    { key: 'needs', label: 'Needs' },
    { key: 'kernel', label: 'Kernel' },
    { key: 'flow', label: 'Flow' },
    { key: 'governance', label: 'Governance' },
];

const ADMIN_VIEWS: { key: AdminView; label: string }[] = [
    { key: 'business', label: 'Business Models' },
    { key: 'i18n', label: 'I18n' },
    { key: 'self-model', label: 'System Self-Model' },
];

export type Lang = 'en' | 'ko';

interface TopNavProps {
    section: Section;
    subView: SubView;
    onNavigate: (section: Section, subView: SubView) => void;
    onGoHome?: () => void;
    onToggleSidePanel: () => void;
    sidePanelOpen: boolean;
    lang: Lang;
    onToggleLang: () => void;
    profiles?: { name: string; version: string }[];
    selectedProfile?: string;
    onSelectProfile?: (name: string) => void;
}

const sectionBtnStyle = (active: boolean) => ({
    padding: '6px 14px',
    fontSize: 13,
    fontWeight: (active ? 700 : 500) as number,
    border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
    borderRadius: 6,
    background: active ? 'var(--muted)' : 'var(--card)',
    color: active ? 'var(--primary)' : 'var(--muted-foreground)',
    cursor: 'pointer' as const,
});

const subBtnStyle = (active: boolean) => ({
    padding: '4px 10px',
    fontSize: 12,
    fontWeight: (active ? 600 : 400) as number,
    border: 'none',
    borderBottom: active ? '2px solid var(--primary)' : '2px solid transparent',
    background: 'none',
    color: active ? 'var(--foreground)' : 'var(--muted-foreground)',
    cursor: 'pointer' as const,
});

function CopyBtn({ value, title }: { value: string; title?: string }) {
    const [copied, setCopied] = useState(false);
    const onClick = useCallback(() => {
        navigator.clipboard.writeText(value).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
        });
    }, [value]);
    return (
        <button
            onClick={onClick}
            title={title || 'Copy'}
            style={{
                width: 26, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '1px solid var(--border)', borderRadius: 4,
                background: copied ? 'var(--status-success-bg)' : 'var(--card)',
                cursor: 'pointer', fontSize: 12, color: copied ? 'var(--status-success-text)' : 'var(--muted-foreground)',
                transition: 'background 0.2s, color 0.2s',
            }}
        >
            {copied ? '\u2713' : '\u2398'}
        </button>
    );
}

const langBtnStyle = (active: boolean) => ({
    padding: '3px 8px',
    fontSize: 11,
    fontWeight: (active ? 700 : 400) as number,
    border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
    borderRadius: 4,
    background: active ? 'var(--muted)' : 'var(--card)',
    color: active ? 'var(--primary)' : 'var(--muted-foreground)',
    cursor: 'pointer' as const,
});

function getViews(section: Section) {
    switch (section) {
        case 'explorer': return EXPLORER_VIEWS;
        case 'needs': return NEEDS_VIEWS;
        case 'governance': return GOVERNANCE_VIEWS;
        case 'status': return STATUS_VIEWS;
        case 'schema': return SCHEMA_VIEWS;
        case 'admin': return ADMIN_VIEWS;
    }
}

/* ---- Hamburger icon (three horizontal bars) ---- */
function HamburgerIcon({ open }: { open: boolean }) {
    const bar: React.CSSProperties = {
        display: 'block',
        width: 18,
        height: 2,
        background: 'var(--muted-foreground)',
        borderRadius: 1,
        transition: 'transform 0.2s, opacity 0.2s',
    };
    return (
        <span style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ ...bar, transform: open ? 'translateY(6px) rotate(45deg)' : 'none' }} />
            <span style={{ ...bar, opacity: open ? 0 : 1 }} />
            <span style={{ ...bar, transform: open ? 'translateY(-6px) rotate(-45deg)' : 'none' }} />
        </span>
    );
}

/* ---- Mobile menu item styles ---- */
const mobileSectionStyle = (active: boolean): React.CSSProperties => ({
    display: 'block',
    width: '100%',
    padding: '10px 16px',
    fontSize: 14,
    fontWeight: active ? 700 : 500,
    background: active ? 'var(--muted)' : 'transparent',
    color: active ? 'var(--primary)' : 'var(--foreground)',
    border: 'none',
    borderLeft: active ? '3px solid var(--primary)' : '3px solid transparent',
    textAlign: 'left',
    cursor: 'pointer',
});

const mobileSubStyle = (active: boolean): React.CSSProperties => ({
    display: 'block',
    width: '100%',
    padding: '8px 16px 8px 32px',
    fontSize: 13,
    fontWeight: active ? 600 : 400,
    background: active ? 'var(--secondary)' : 'transparent',
    color: active ? 'var(--primary)' : 'var(--muted-foreground)',
    border: 'none',
    textAlign: 'left',
    cursor: 'pointer',
});

export default function TopNav({
    section, subView, onNavigate, onGoHome, onToggleSidePanel, sidePanelOpen,
    lang, onToggleLang,
    profiles, selectedProfile, onSelectProfile,
}: TopNavProps) {
    const isDashboard = !subView;
    const views = getViews(section);
    const showProfileSelector = subView === 'profile-graph' && profiles && profiles.length > 0;
    const { theme, toggleTheme } = useTheme();

    const isMobile = useMediaQuery('(max-width: 767px)');
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    // Close mobile menu when switching to desktop
    useEffect(() => {
        if (!isMobile) setMenuOpen(false);
    }, [isMobile]);

    // Close mobile menu on outside click
    useEffect(() => {
        if (!menuOpen) return;
        const handler = (e: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setMenuOpen(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [menuOpen]);

    const handleNavigate = useCallback((sec: Section, sv: SubView) => {
        setMenuOpen(false);
        onNavigate(sec, sv);
    }, [onNavigate]);

    const handleGoHome = useCallback(() => {
        setMenuOpen(false);
        onGoHome?.();
    }, [onGoHome]);

    /* ---- MOBILE layout ---- */
    if (isMobile) {
        return (
            <div ref={menuRef} style={{
                position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
                fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                {/* Top bar */}
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
                    background: 'var(--background)', borderBottom: '1px solid var(--border)',
                }}>
                    <button
                        onClick={onToggleSidePanel}
                        style={{
                            width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            border: '1px solid var(--border)', borderRadius: 6, background: sidePanelOpen ? 'var(--secondary)' : 'var(--card)',
                            cursor: 'pointer', fontSize: 14, color: 'var(--muted-foreground)',
                        }}
                        title="Toggle side panel"
                    >
                        {sidePanelOpen ? '\u25C1' : '\u25B7'}
                    </button>
                    <button
                        onClick={handleGoHome}
                        style={{
                            fontSize: 14, fontWeight: 700, color: 'var(--foreground)',
                            background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                            fontFamily: 'inherit',
                        }}
                    >
                        EA-Sys
                    </button>

                    {/* Current section indicator */}
                    {!isDashboard && (
                        <span style={{ fontSize: 12, color: 'var(--muted-foreground)', fontWeight: 500 }}>
                            / {SECTIONS.find(s => s.key === section)?.label}
                        </span>
                    )}

                    {/* Spacer */}
                    <div style={{ flex: 1 }} />

                    {/* Hamburger toggle */}
                    <button
                        onClick={() => setMenuOpen(prev => !prev)}
                        style={{
                            width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            border: '1px solid var(--border)', borderRadius: 6,
                            background: menuOpen ? 'var(--secondary)' : 'var(--card)',
                            cursor: 'pointer',
                        }}
                        title="Toggle menu"
                    >
                        <HamburgerIcon open={menuOpen} />
                    </button>
                </div>

                {/* Slide-down dropdown */}
                <div style={{
                    maxHeight: menuOpen ? 500 : 0,
                    overflow: 'hidden',
                    transition: 'max-height 0.25s ease-in-out',
                    background: 'var(--background)',
                    borderBottom: menuOpen ? '1px solid var(--border)' : 'none',
                    boxShadow: menuOpen ? `0 4px 12px var(--shadow-md)` : 'none',
                }}>
                    {/* Section buttons */}
                    {SECTIONS.map((s) => (
                        <div key={s.key}>
                            <button
                                onClick={() => handleNavigate(s.key, s.defaultSub)}
                                style={mobileSectionStyle(!isDashboard && section === s.key)}
                            >
                                {s.label}
                            </button>
                            {/* Sub-views for active section */}
                            {!isDashboard && section === s.key && (
                                <div style={{ background: 'var(--secondary)' }}>
                                    {getViews(s.key).map((v) => (
                                        <button
                                            key={v.key}
                                            onClick={() => handleNavigate(s.key, v.key)}
                                            style={mobileSubStyle(subView === v.key)}
                                        >
                                            {v.label}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Divider */}
                    <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />

                    {/* Profile selector in mobile menu */}
                    {showProfileSelector && (
                        <div style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted-foreground)', textTransform: 'uppercase' }}>Profile</span>
                            <select
                                value={selectedProfile}
                                onChange={(e) => {
                                    onSelectProfile?.(e.target.value);
                                    setMenuOpen(false);
                                }}
                                style={{ flex: 1, padding: '4px 8px', fontSize: 12, border: '1px solid var(--border)', borderRadius: 4, background: 'var(--card)', color: 'var(--foreground)' }}
                            >
                                {profiles!.map((p) => (
                                    <option key={p.name} value={p.name}>{p.name} (v{p.version})</option>
                                ))}
                            </select>
                            <CopyBtn value={selectedProfile || ''} title="Copy profile name" />
                        </div>
                    )}

                    {/* Language toggle + Theme toggle in mobile menu */}
                    <div style={{ padding: '8px 16px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <button
                            onClick={toggleTheme}
                            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                            style={{
                                width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center',
                                border: '1px solid var(--border)', borderRadius: 4,
                                background: 'var(--card)', cursor: 'pointer',
                                fontSize: 14, color: 'var(--muted-foreground)',
                            }}
                        >
                            {theme === 'dark' ? '\u2600' : '\u263E'}
                        </button>
                        <button onClick={lang === 'en' ? undefined : onToggleLang} style={langBtnStyle(lang === 'en')}>EN</button>
                        <button onClick={lang === 'ko' ? undefined : onToggleLang} style={langBtnStyle(lang === 'ko')}>KO</button>
                    </div>
                </div>

                {/* Backdrop overlay when menu is open */}
                {menuOpen && (
                    <div
                        onClick={() => setMenuOpen(false)}
                        style={{
                            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                            zIndex: -1,
                        }}
                    />
                )}
            </div>
        );
    }

    /* ---- DESKTOP layout (original) ---- */
    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
            background: 'var(--background)', borderBottom: '1px solid var(--border)',
            fontFamily: 'system-ui, -apple-system, sans-serif',
        }}>
            {/* Primary row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 16px' }}>
                <button
                    onClick={onToggleSidePanel}
                    style={{
                        width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        border: '1px solid var(--border)', borderRadius: 6, background: sidePanelOpen ? 'var(--secondary)' : 'var(--card)',
                        cursor: 'pointer', fontSize: 14, color: 'var(--muted-foreground)',
                    }}
                    title="Toggle side panel"
                >
                    {sidePanelOpen ? '\u25C1' : '\u25B7'}
                </button>
                <button
                    onClick={onGoHome}
                    style={{
                        fontSize: 14, fontWeight: 700, color: 'var(--foreground)', marginRight: 8,
                        background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                        fontFamily: 'inherit',
                    }}
                >
                    EA-Sys
                </button>
                <button onClick={() => onNavigate('explorer', 'kernel-schema')} style={sectionBtnStyle(!isDashboard && section === 'explorer')}>Explorer</button>
                <button onClick={() => onNavigate('needs', 'catalog')} style={sectionBtnStyle(!isDashboard && section === 'needs')}>Needs</button>
                <button onClick={() => onNavigate('governance', 'rule-lifecycle')} style={sectionBtnStyle(!isDashboard && section === 'governance')}>Governance</button>
                <button onClick={() => onNavigate('schema', 'kernel')} style={sectionBtnStyle(!isDashboard && section === 'schema')}>Schema</button>
                <button onClick={() => onNavigate('status', 'entities')} style={sectionBtnStyle(!isDashboard && section === 'status')}>Status</button>
                <button onClick={() => onNavigate('admin', 'business')} style={sectionBtnStyle(!isDashboard && section === 'admin')}>Admin</button>

                {/* Theme toggle + Language toggle -- right-aligned */}
                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
                    <button
                        onClick={toggleTheme}
                        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                        style={{
                            width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            border: '1px solid var(--border)', borderRadius: 4,
                            background: 'var(--card)', cursor: 'pointer',
                            fontSize: 14, color: 'var(--muted-foreground)',
                        }}
                    >
                        {theme === 'dark' ? '\u2600' : '\u263E'}
                    </button>
                    <div style={{ display: 'flex', gap: 2 }}>
                        <button onClick={lang === 'en' ? undefined : onToggleLang} style={langBtnStyle(lang === 'en')}>EN</button>
                        <button onClick={lang === 'ko' ? undefined : onToggleLang} style={langBtnStyle(lang === 'ko')}>KO</button>
                    </div>
                </div>

                {showProfileSelector && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted-foreground)', textTransform: 'uppercase' }}>Profile</span>
                        <select
                            value={selectedProfile}
                            onChange={(e) => onSelectProfile?.(e.target.value)}
                            style={{ padding: '4px 8px', fontSize: 12, border: '1px solid var(--border)', borderRadius: 4, background: 'var(--card)', color: 'var(--foreground)', maxWidth: 220 }}
                        >
                            {profiles!.map((p) => (
                                <option key={p.name} value={p.name}>{p.name} (v{p.version})</option>
                            ))}
                        </select>
                        <CopyBtn value={selectedProfile || ''} title="Copy profile name" />
                    </div>
                )}
            </div>

            {/* Sub-view row */}
            {!isDashboard && (
                <div style={{ display: 'flex', gap: 4, padding: '0 16px 0 58px', borderTop: '1px solid var(--border)' }}>
                    {views.map((v) => (
                        <button key={v.key} onClick={() => onNavigate(section, v.key)} style={subBtnStyle(subView === v.key)}>{v.label}</button>
                    ))}
                </div>
            )}
        </div>
    );
}
