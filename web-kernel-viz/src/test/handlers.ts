import { http, HttpResponse } from 'msw';

import type {
    ProfileListItem,
    GovernanceDashboardResponse,
    KernelEntitiesResponse,
    KernelRelationsResponse,
    CrossLayerSummaryResponse,
    NeedsCatalogSummary,
} from '@/api/types';

// --- Mock Data ---

export const mockProfiles: ProfileListItem[] = [
    { name: 'ea-sys-kernel', version: '0.1.0' },
    { name: 'ea-sys-flow', version: '0.1.0' },
];

export const mockDashboard: GovernanceDashboardResponse = {
    managed_layers: {
        layers: [
            {
                layer_key: 'kernel',
                profile_name: 'ea-sys-kernel',
                loaded: true,
                name: 'Kernel',
                version: '0.1.0',
                element_count: 12,
                relation_count: 5,
                rule_count: 20,
            },
            {
                layer_key: 'flow',
                profile_name: 'ea-sys-flow',
                loaded: true,
                name: 'Flow',
                version: '0.1.0',
                element_count: 8,
                relation_count: 3,
                rule_count: 10,
            },
        ],
        governance_stack: [],
        total_profiles: 2,
    },
    schema: {
        entity_count: 15,
        relation_count: 6,
        entities: ['Element', 'Relation', 'Rule'],
        relations: ['composition', 'dependency'],
    },
    frameworks: [
        {
            name: 'TOGAF',
            version: '10.0',
            element_count: 5,
            relation_count: 2,
            rule_count: 8,
        },
    ],
};

export const mockCrossLayerSummary: CrossLayerSummaryResponse = {
    layers: [
        {
            layer_key: 'kernel',
            loaded: true,
            node_count: 12,
            edge_count: 18,
            top_relations: [{ relation: 'composition', count: 10 }],
        },
    ],
    total_nodes: 12,
    total_edges: 18,
};

export const mockEntities: KernelEntitiesResponse = {
    total: 3,
    layers: [
        {
            name: 'kernel',
            count: 3,
            entities: [
                { name: 'Element', parent: null, is_abstract: true, description: 'Base element', display_name: null },
                { name: 'Entity', parent: 'Element', is_abstract: false, description: 'Concrete entity', display_name: null },
                { name: 'Relation', parent: 'Element', is_abstract: false, description: 'Relation type', display_name: null },
            ],
        },
    ],
};

export const mockRelations: KernelRelationsResponse = {
    total: 2,
    layers: [
        {
            name: 'kernel',
            count: 2,
            relations: [
                {
                    name: 'composition',
                    parent: null,
                    roles: [
                        { name: 'whole', player: 'Entity' },
                        { name: 'part', player: 'Entity' },
                    ],
                    owns: [],
                    owns_key: null,
                    description: 'Composition relation',
                    display_name: null,
                },
                {
                    name: 'dependency',
                    parent: null,
                    roles: [
                        { name: 'client', player: 'Entity' },
                        { name: 'supplier', player: 'Entity' },
                    ],
                    owns: [],
                    owns_key: null,
                    description: 'Dependency relation',
                    display_name: null,
                },
            ],
        },
    ],
};

export const mockNeedsCatalogs: NeedsCatalogSummary[] = [
    {
        id: 'cat-1',
        name: 'Core Requirements',
        description: 'Core system requirements',
        needs_count: 5,
        stakeholder_count: 2,
        use_case_count: 3,
        updated_at: '2026-01-01T00:00:00Z',
    },
];

const API_URL = 'http://localhost:9000';

// --- Handlers ---

export const handlers = [
    http.get(`${API_URL}/profiles`, () => {
        return HttpResponse.json(mockProfiles);
    }),

    http.get(`${API_URL}/governance/dashboard`, () => {
        return HttpResponse.json(mockDashboard);
    }),

    http.get(`${API_URL}/governance/layers/summary`, () => {
        return HttpResponse.json(mockCrossLayerSummary);
    }),

    http.get(`${API_URL}/kernel/entities`, () => {
        return HttpResponse.json(mockEntities);
    }),

    http.get(`${API_URL}/kernel/relations`, () => {
        return HttpResponse.json(mockRelations);
    }),

    http.get(`${API_URL}/needs/catalogs`, () => {
        return HttpResponse.json(mockNeedsCatalogs);
    }),

    http.get(`${API_URL}/rules`, () => {
        return HttpResponse.json([]);
    }),

    http.get(`${API_URL}/automation/promotions`, () => {
        return HttpResponse.json([]);
    }),
];
