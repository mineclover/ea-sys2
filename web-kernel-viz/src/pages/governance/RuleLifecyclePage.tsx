
import { RuleLifecycleView } from '@/components/governance';
import { useAppState } from '@/contexts/AppStateContext';

export default function RuleLifecyclePage() {
    const { showDetail } = useAppState();
    return <RuleLifecycleView onShowDetail={showDetail} />;
}
