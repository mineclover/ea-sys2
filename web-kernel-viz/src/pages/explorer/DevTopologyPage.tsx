
import ProfileGraph from '@/components/ProfileGraph';
import { useAppState } from '@/contexts/AppStateContext';
import { PageHeader } from '@/components/layout';

export default function DevTopologyPage() {
    const { lang } = useAppState();
    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <PageHeader metaKey="explorer.dev-topology" compact />
            <div style={{ flex: 1, minHeight: 0 }}>
                <ProfileGraph profileName="EASystem-Development" lang={lang} />
            </div>
        </div>
    );
}
