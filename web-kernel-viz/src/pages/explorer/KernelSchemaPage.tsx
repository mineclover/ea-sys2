
import FlowGraph from '@/components/FlowGraph';
import { useAppState } from '@/contexts/AppStateContext';

export default function KernelSchemaPage() {
    const { lang } = useAppState();
    return <FlowGraph lang={lang} />;
}
