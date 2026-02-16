
import { BusinessFlowView } from '@/components/governance';
import { useAppState } from '@/contexts/AppStateContext';

export default function BusinessFlowPage() {
    const { lang } = useAppState();
    return <BusinessFlowView lang={lang} />;
}
