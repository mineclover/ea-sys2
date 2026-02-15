
import { useState, useCallback } from 'react';

export type Section = 'explorer' | 'needs' | 'governance';

export type ExplorerView = 'kernel-schema' | 'profile-graph' | 'rules';
export type NeedsView = 'catalog';
export type GovernanceView = 'rule-lifecycle' | 'models' | 'decisions' | 'simulation';
export type SubView = ExplorerView | NeedsView | GovernanceView;

const EXPLORER_VIEWS: { key: ExplorerView; label: string }[] = [
    { key: 'kernel-schema', label: 'Kernel Schema' },
    { key: 'profile-graph', label: 'Profile Graph' },
    { key: 'rules', label: 'Rules' },
];

const NEEDS_VIEWS: { key: NeedsView; label: string }[] = [
    { key: 'catalog', label: 'Needs Catalog' },
];

const GOVERNANCE_VIEWS: { key: GovernanceView; label: string }[] = [
    { key: 'rule-lifecycle', label: 'Rule Lifecycle' },
    { key: 'models', label: 'Models' },
    { key: 'decisions', label: 'Decisions' },
    { key: 'simulation', label: 'Simulation' },
];

export type Lang = 'en' | 'ko';

interface TopNavProps {
    section: Section;
    subView: SubView;
    onNavigate: (section: Section, subView: SubView) => void;
    onToggleSidePanel: () => void;
    sidePanelOpen: boolean;
    lang: Lang;
    onToggleLang: () => void;
    // Profile selector (shown when profile-graph is active)
    profiles?: { name: string; version: string }[];
    selectedProfile?: string;
    onSelectProfile?: (name: string) => void;
}

const sectionBtnStyle = (active: boolean) => ({
    padding: '6px 14px',
    fontSize: 13,
    fontWeight: (active ? 700 : 500) as number,
    border: `1px solid ${active ? '#3b82f6' : '#cbd5e1'}`,
    borderRadius: 6,
    background: active ? '#eff6ff' : '#fff',
    color: active ? '#3b82f6' : '#475569',
    cursor: 'pointer' as const,
});

const subBtnStyle = (active: boolean) => ({
    padding: '4px 10px',
    fontSize: 12,
    fontWeight: (active ? 600 : 400) as number,
    border: 'none',
    borderBottom: active ? '2px solid #3b82f6' : '2px solid transparent',
    background: 'none',
    color: active ? '#1e293b' : '#94a3b8',
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
                border: '1px solid #e2e8f0', borderRadius: 4,
                background: copied ? '#dcfce7' : '#fff',
                cursor: 'pointer', fontSize: 12, color: copied ? '#166534' : '#64748b',
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
    border: `1px solid ${active ? '#3b82f6' : '#e2e8f0'}`,
    borderRadius: 4,
    background: active ? '#eff6ff' : '#fff',
    color: active ? '#3b82f6' : '#94a3b8',
    cursor: 'pointer' as const,
});

export default function TopNav({
    section, subView, onNavigate, onToggleSidePanel, sidePanelOpen,
    lang, onToggleLang,
    profiles, selectedProfile, onSelectProfile,
}: TopNavProps) {
    const views = section === 'explorer' ? EXPLORER_VIEWS : section === 'needs' ? NEEDS_VIEWS : GOVERNANCE_VIEWS;
    const showProfileSelector = subView === 'profile-graph' && profiles && profiles.length > 0;

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
            background: '#fff', borderBottom: '1px solid #e2e8f0',
            fontFamily: 'system-ui, -apple-system, sans-serif',
        }}>
            {/* Primary row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 16px' }}>
                <button
                    onClick={onToggleSidePanel}
                    style={{
                        width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        border: '1px solid #e2e8f0', borderRadius: 6, background: sidePanelOpen ? '#f1f5f9' : '#fff',
                        cursor: 'pointer', fontSize: 14, color: '#64748b',
                    }}
                    title="Toggle side panel"
                >
                    {sidePanelOpen ? '\u25C1' : '\u25B7'}
                </button>
                <span style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginRight: 8 }}>EA-Sys</span>
                <button
                    onClick={() => onNavigate('explorer', 'kernel-schema')}
                    style={sectionBtnStyle(section === 'explorer')}
                >
                    Explorer
                </button>
                <button
                    onClick={() => onNavigate('needs', 'catalog')}
                    style={sectionBtnStyle(section === 'needs')}
                >
                    Needs
                </button>
                <button
                    onClick={() => onNavigate('governance', 'rule-lifecycle')}
                    style={sectionBtnStyle(section === 'governance')}
                >
                    Governance
                </button>

                {/* Language toggle + Profile selector — right-aligned */}
                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ display: 'flex', gap: 2 }}>
                        <button onClick={lang === 'en' ? undefined : onToggleLang} style={langBtnStyle(lang === 'en')}>EN</button>
                        <button onClick={lang === 'ko' ? undefined : onToggleLang} style={langBtnStyle(lang === 'ko')}>KO</button>
                    </div>
                </div>

                {/* Profile selector (shown when profile-graph is active) */}
                {showProfileSelector && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase' }}>
                            Profile
                        </span>
                        <select
                            value={selectedProfile}
                            onChange={(e) => onSelectProfile?.(e.target.value)}
                            style={{
                                padding: '4px 8px', fontSize: 12,
                                border: '1px solid #cbd5e1', borderRadius: 4,
                                background: '#fff', color: '#1e293b',
                                maxWidth: 220,
                            }}
                        >
                            {profiles.map((p) => (
                                <option key={p.name} value={p.name}>
                                    {p.name} (v{p.version})
                                </option>
                            ))}
                        </select>
                        <CopyBtn value={selectedProfile || ''} title="Copy profile name" />
                    </div>
                )}
            </div>

            {/* Sub-view row */}
            <div style={{ display: 'flex', gap: 4, padding: '0 16px 0 58px', borderTop: '1px solid #f1f5f9' }}>
                {views.map((v) => (
                    <button
                        key={v.key}
                        onClick={() => onNavigate(section, v.key)}
                        style={subBtnStyle(subView === v.key)}
                    >
                        {v.label}
                    </button>
                ))}
            </div>
        </div>
    );
}
