
import type { ReactNode } from 'react';

interface Column<T> {
    key: string;
    header: string;
    render: (item: T) => ReactNode;
    width?: string | number;
}

interface DataTableProps<T> {
    data: T[];
    columns: Column<T>[];
    keyFn: (item: T) => string;
    onRowClick?: (item: T) => void;
    emptyMessage?: string;
}

export default function DataTable<T>({ data, columns, keyFn, onRowClick, emptyMessage = 'No items.' }: DataTableProps<T>) {
    if (data.length === 0) {
        return <div style={{ padding: 16, fontSize: 13, color: 'var(--muted-foreground)' }}>{emptyMessage}</div>;
    }

    return (
        <div style={{ overflow: 'auto' }}>
            <table style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 12,
                fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <thead>
                    <tr>
                        {columns.map((col) => (
                            <th key={col.key} scope="col" style={{
                                textAlign: 'left',
                                padding: '8px 12px',
                                fontSize: 10,
                                fontWeight: 700,
                                color: 'var(--muted-foreground)',
                                textTransform: 'uppercase',
                                borderBottom: '1px solid var(--border)',
                                width: col.width,
                            }}>
                                {col.header}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {data.map((item) => (
                        <tr
                            key={keyFn(item)}
                            onClick={onRowClick ? () => onRowClick(item) : undefined}
                            onKeyDown={onRowClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowClick(item); } } : undefined}
                            tabIndex={onRowClick ? 0 : undefined}
                            role={onRowClick ? 'button' : undefined}
                            style={{
                                cursor: onRowClick ? 'pointer' : 'default',
                                borderBottom: '1px solid var(--accent)',
                            }}
                            onMouseEnter={(e) => { if (onRowClick) (e.currentTarget.style.background = 'var(--secondary)'); }}
                            onMouseLeave={(e) => { if (onRowClick) (e.currentTarget.style.background = ''); }}
                        >
                            {columns.map((col) => (
                                <td key={col.key} style={{ padding: '10px 12px', color: 'var(--foreground)' }}>
                                    {col.render(item)}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
