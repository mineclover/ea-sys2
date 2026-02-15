
export type Section = 'explorer' | 'governance';

export type ExplorerView = 'kernel-schema' | 'profile-graph' | 'rules';
export type GovernanceView = 'rule-lifecycle' | 'models' | 'decisions' | 'simulation';
export type SubView = ExplorerView | GovernanceView;

const EXPLORER_VIEWS: { key: ExplorerView; label: string }[] = [
    { key: 'kernel-schema', label: 'Kernel Schema' },
    { key: 'profile-graph', label: 'Profile Graph' },
    { key: 'rules', label: 'Rules' },
];

const GOVERNANCE_VIEWS: { key: GovernanceView; label: string }[] = [
    { key: 'rule-lifecycle', label: 'Rule Lifecycle' },
    { key: 'models', label: 'Models' },
    { key: 'decisions', label: 'Decisions' },
    { key: 'simulation', label: 'Simulation' },
];

interface TopNavProps {
    section: Section;
    subView: SubView;
    onNavigate: (section: Section, subView: SubView) => void;
    onToggleSidePanel: () => void;
    sidePanelOpen: boolean;
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

export default function TopNav({ section, subView, onNavigate, onToggleSidePanel, sidePanelOpen }: TopNavProps) {
    const views = section === 'explorer' ? EXPLORER_VIEWS : GOVERNANCE_VIEWS;

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
                    onClick={() => onNavigate('governance', 'rule-lifecycle')}
                    style={sectionBtnStyle(section === 'governance')}
                >
                    Governance
                </button>
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
