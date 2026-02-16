
import ProfileGraph from '@/components/ProfileGraph';
import { useAppState } from '@/contexts/AppStateContext';

export default function DevTopologyPage() {
    const { lang } = useAppState();
    return <ProfileGraph profileName="EASystem-Development" lang={lang} />;
}
