
import { ImpactAnalysisView } from '@/components/governance';
import { useAppState } from '@/contexts/AppStateContext';

export default function ImpactAnalysisPage() {
    const { showDetail } = useAppState();
    return <ImpactAnalysisView onShowDetail={showDetail} />;
}
