import type { DiagramStyle, NodeStyle } from '../types/diagram';

export interface KernelRole {
    name: string;
    player: string;
}

export interface KernelEntity {
    name: string;
    layer: string;
    parent?: string;
    description?: string;
    isAbstract?: boolean;
    style?: NodeStyle;
}

export interface KernelRelation {
    name: string;
    layer: string;
    parent?: string;
    description?: string;
    roles?: KernelRole[];
    style?: DiagramStyle;
}

export const KERNEL_ENTITIES: KernelEntity[] = [
    // L1 Structure
    {
        name: 'element',
        layer: 'L1',
        description: 'Root of all kernel elements',
        isAbstract: true,
        style: { shape: 'rounded', backgroundColor: '#f3f4f6', borderColor: '#9ca3af' }
    },
    {
        name: 'namespace',
        layer: 'L1',
        parent: 'element',
        description: 'Element that can contain other named elements',
        isAbstract: true,
        style: { shape: 'rounded' }
    },
    {
        name: 'metatype',
        layer: 'L1',
        parent: 'namespace',
        description: 'Classifies instances — KerML Type equivalent',
        isAbstract: true,
        style: { shape: 'rectangle', borderWidth: 2 }
    },
    { name: 'feature', layer: 'L1', parent: 'metatype', description: 'Typed characteristic of a metatype — KerML Feature' },
    {
        name: 'port',
        layer: 'L1',
        parent: 'feature',
        description: 'Access or interaction point exposed by a structure',
        style: { shape: 'circle', width: 60, height: 60 }
    },
    { name: 'classifier', layer: 'L1', parent: 'metatype', description: 'Metatype that can be instantiated', isAbstract: true },
    {
        name: 'structure',
        layer: 'L1',
        parent: 'classifier',
        description: 'Active structured classifier — equivalent to UML Class',
        style: { shape: 'rectangle', borderWidth: 2 }
    },
    { name: 'item', layer: 'L1', parent: 'classifier', description: 'Passive classifier with identity — data-bearing object' },
    { name: 'datatype', layer: 'L1', parent: 'classifier', description: 'Value type without identity' },
    {
        name: 'package',
        layer: 'L1',
        parent: 'namespace',
        description: 'Concrete namespace container — groups elements',
        style: { shape: 'rounded', borderWidth: 2 }
    },
    // L4 Concrete
    {
        name: 'step',
        layer: 'L4',
        parent: 'feature',
        description: 'Unit of behavior — a feature that participates in successions',
        style: { shape: 'rounded' }
    },
    {
        name: 'action',
        layer: 'L4',
        parent: 'step',
        description: 'Executable step — concrete unit of computation',
        style: { shape: 'rectangle', borderWidth: 2 }
    },
    {
        name: 'event',
        layer: 'L4',
        parent: 'feature',
        description: 'State change occurrence that triggers behavior',
        style: { shape: 'diamond', width: 120, height: 80 }
    },
    { name: 'expression', layer: 'L4', parent: 'feature', description: 'Evaluatable value computation' },
    {
        name: 'state',
        layer: 'L4',
        parent: 'metatype',
        description: 'Behavioral state — classifies situations within a lifecycle',
        style: { shape: 'rounded', width: 140, height: 60 }
    },
];

export const KERNEL_RELATIONS: KernelRelation[] = [
    // L2 Relationship
    {
        name: 'membership', layer: 'L2', description: 'Element belongs to a namespace',
        roles: [{ name: 'container', player: 'namespace' }, { name: 'member', player: 'element' }]
    },
    {
        name: 'ownership', layer: 'L2', description: 'Compositional ownership of elements',
        roles: [{ name: 'owner', player: 'namespace' }, { name: 'owned', player: 'element' }],
        style: { endMarker: 'composition' }
    },
    {
        name: 'specialization', layer: 'L2', description: 'Subtype relationship — inheritance of features',
        roles: [{ name: 'supertype', player: 'metatype' }, { name: 'subtype', player: 'metatype' }],
        style: { endMarker: 'directed', connector: 'solid' }
    },
    {
        name: 'feature_typing', layer: 'L2', description: 'Feature is typed by a metatype',
        roles: [{ name: 'typed_feature', player: 'feature' }, { name: 'typing', player: 'metatype' }],
        style: { connector: 'dashed', endMarker: 'none' } // Usually shown as :Type
    },
    {
        name: 'association', layer: 'L2', description: 'Structural connection between metatypes',
        roles: [{ name: 'source_end', player: 'metatype' }, { name: 'target_end', player: 'metatype' }],
        style: { connector: 'solid' }
    },
    {
        name: 'connector', layer: 'L2', description: 'Link between features — base for behavioral qualification',
        roles: [{ name: 'source', player: 'feature' }, { name: 'target', player: 'feature' }],
        style: { connector: 'solid' }
    },
    {
        name: 'redefinition', layer: 'L2', description: 'Feature redefines another feature in a specialization context',
        roles: [{ name: 'original', player: 'feature' }, { name: 'redefining', player: 'feature' }],
        style: { connector: 'dashed', startMarker: 'none', endMarker: 'none' } // Often internal property
    },
    {
        name: 'subsetting', layer: 'L2', description: 'Feature values are a subset of another feature values',
        roles: [{ name: 'subsetted', player: 'feature' }, { name: 'subsetting_feature', player: 'feature' }],
        style: { connector: 'dashed' }
    },
    // L3 Behavioral
    {
        name: 'flow', layer: 'L3', parent: 'connector', description: 'Data/object flow along a connector',
        style: { connector: 'solid', endMarker: 'directed' } // Arrow for flow
    },
    {
        name: 'succession', layer: 'L3', parent: 'connector', description: 'Temporal ordering with execution semantics',
        roles: [{ name: 'predecessor', player: 'feature' }, { name: 'successor', player: 'feature' }],
        style: { connector: 'dashed', endMarker: 'directed' }
    },
    {
        name: 'interaction', layer: 'L3', parent: 'connector', description: 'Message exchange between features'
    },
    {
        name: 'triggering', layer: 'L3', description: 'Event triggers a behavioral response',
        roles: [{ name: 'trigger_source', player: 'feature' }, { name: 'responding', player: 'step' }],
        style: { connector: 'dashed', endMarker: 'directed' }
    },
    {
        name: 'guarding', layer: 'L3', description: 'Condition guards a behavioral element',
        roles: [{ name: 'guarded_element', player: 'state' }, { name: 'condition', player: 'expression' }],
        style: { connector: 'dashed', startMarker: 'none' }
    },
    {
        name: 'transition', layer: 'L3', description: 'State transition',
        roles: [{ name: 'source_state', player: 'state' }, { name: 'target_state', player: 'state' }],
        style: { connector: 'solid', endMarker: 'directed' }
    },
];
