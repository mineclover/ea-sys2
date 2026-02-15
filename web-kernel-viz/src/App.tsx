
import { useState, useEffect, useCallback, type ReactNode } from 'react';
import { TopNav, SidePanel, DetailSlideOver } from './components/layout';
import type { Section, SubView } from './components/layout/TopNav';
import FlowGraph from './components/FlowGraph';
import ProfileGraph from './components/ProfileGraph';
import ProfileSidePanel from './components/ProfileSidePanel';
import RulesView from './components/RulesView';
import { RuleLifecycleView, ModelsView, DecisionsView, SimulationView } from './components/governance';
import { fetchProfiles } from './api/client';
import type { ProfileListItem } from './api/types';

function App() {
    const [section, setSection] = useState<Section>('explorer');
    const [subView, setSubView] = useState<SubView>('kernel-schema');
    const [sidePanelOpen, setSidePanelOpen] = useState(false);

    // Detail slide-over
    const [detailOpen, setDetailOpen] = useState(false);
    const [detailTitle, setDetailTitle] = useState('');
    const [detailContent, setDetailContent] = useState<ReactNode>(null);

    // Profile state (for profile-graph sub-view)
    const [profiles, setProfiles] = useState<ProfileListItem[]>([]);
    const [selectedProfile, setSelectedProfile] = useState('');
    const ALL_LAYERS = ['Infra', 'Governance', 'Decision', 'Needs', 'Kernel', 'Flow'];
    const [visibleLayers, setVisibleLayers] = useState<Set<string>>(new Set(ALL_LAYERS));
    const [crossLayerOnly, setCrossLayerOnly] = useState(false);

    const onToggleLayer = useCallback((layer: string) => {
        setVisibleLayers((prev) => {
            const next = new Set(prev);
            if (next.has(layer)) {
                next.delete(layer);
            } else {
                next.add(layer);
            }
            return next;
        });
    }, []);

    useEffect(() => {
        if (subView === 'profile-graph' && profiles.length === 0) {
            fetchProfiles()
                .then((list) => {
                    setProfiles(list);
                    if (list.length > 0 && !selectedProfile) {
                        const eaSys = list.find((p) => p.name.startsWith('EASystem-'));
                        setSelectedProfile(eaSys?.name || list[0].name);
                    }
                })
                .catch(() => {});
        }
    }, [subView, profiles.length, selectedProfile]);

    const onNavigate = useCallback((sec: Section, sv: SubView) => {
        setSection(sec);
        setSubView(sv);
        setDetailOpen(false);
        setDetailContent(null);
        // Auto-open side panel for profile-graph view
        if (sv === 'profile-graph') {
            setSidePanelOpen(true);
        }
    }, []);

    const onShowDetail = useCallback((title: string, content: ReactNode) => {
        setDetailTitle(title);
        setDetailContent(content);
        setDetailOpen(true);
    }, []);

    const onCloseDetail = useCallback(() => {
        setDetailOpen(false);
    }, []);

    // Side panel content based on current view
    const renderSidePanel = () => {
        switch (subView) {
            case 'profile-graph':
                return (
                    <ProfileSidePanel
                        profileName={selectedProfile}
                        visibleLayers={visibleLayers}
                        onToggleLayer={onToggleLayer}
                        crossLayerOnly={crossLayerOnly}
                        onToggleCrossLayer={() => setCrossLayerOnly((v) => !v)}
                    />
                );
            default:
                return (
                    <div style={{ color: '#94a3b8', fontSize: 12 }}>
                        Filters and controls for the current view.
                    </div>
                );
        }
    };

    // Main content
    const renderMain = () => {
        switch (subView) {
            case 'kernel-schema':
                return <FlowGraph />;
            case 'profile-graph':
                return selectedProfile
                    ? <ProfileGraph profileName={selectedProfile} visibleLayers={visibleLayers} crossLayerOnly={crossLayerOnly} onShowDetail={onShowDetail} />
                    : <div style={{ padding: 40, color: '#94a3b8', fontFamily: 'system-ui' }}>Loading profiles...</div>;
            case 'rules':
                return <RulesView onShowDetail={onShowDetail} sidePanel={null} />;
            case 'rule-lifecycle':
                return <RuleLifecycleView onShowDetail={onShowDetail} />;
            case 'models':
                return <ModelsView onShowDetail={onShowDetail} />;
            case 'decisions':
                return <DecisionsView onShowDetail={onShowDetail} />;
            case 'simulation':
                return <SimulationView onShowDetail={onShowDetail} />;
            default:
                return null;
        }
    };

    return (
        <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
            <TopNav
                section={section}
                subView={subView}
                onNavigate={onNavigate}
                onToggleSidePanel={() => setSidePanelOpen((v) => !v)}
                sidePanelOpen={sidePanelOpen}
                profiles={profiles.map((p) => ({ name: p.name, version: p.version }))}
                selectedProfile={selectedProfile}
                onSelectProfile={setSelectedProfile}
            />

            {/* Main area below nav (nav height ~76px) */}
            <div style={{ marginTop: 76, flex: 1, display: 'flex', overflow: 'hidden' }}>
                <SidePanel open={sidePanelOpen}>
                    {renderSidePanel()}
                </SidePanel>

                <div style={{ flex: 1, overflow: 'hidden' }}>
                    {renderMain()}
                </div>
            </div>

            <DetailSlideOver open={detailOpen} onClose={onCloseDetail} title={detailTitle}>
                {detailContent}
            </DetailSlideOver>
        </div>
    );
}

export default App;
