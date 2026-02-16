
import { useParams } from 'react-router-dom';
import FlowGraph from '@/components/FlowGraph';
import { LayerSchemaView } from '@/components/schema';
import { useAppState } from '@/contexts/AppStateContext';

export default function SchemaPage() {
    const { layerKey } = useParams<{ layerKey: string }>();
    const { lang } = useAppState();

    if (layerKey === 'kernel') {
        return <FlowGraph lang={lang} />;
    }

    return <LayerSchemaView layerKey={layerKey || 'kernel'} lang={lang} />;
}
