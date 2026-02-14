
export type MarkerType =
    | 'composition' // ◆
    | 'aggregation' // ◇
    | 'assignment'  // ○
    | 'backward'    // ◀
    | 'directed'    // ▶
    | 'weak_directed' // ▷
    | 'provides'    // ●
    | 'constrains'  // ╳
    | 'none';

export type ConnectorType =
    | 'solid'
    | 'spaced'
    | 'dashed'
    | 'double'
    | 'wave';

export type NodeShape = 'rectangle' | 'rounded' | 'circle' | 'diamond' | 'hexagon';

export type PortPosition = 'top' | 'right' | 'bottom' | 'left';

export interface DiagramStyle {
    executionMode?: 'sequential' | 'parallel' | 'async';
    startMarker?: MarkerType;
    endMarker?: MarkerType;
    connector?: ConnectorType;
    strokeColor?: string;
    strokeWidth?: number;
    animated?: boolean;
    opacity?: number;
    labelStyle?: {
        fill?: string;
        fontSize?: number;
        fontWeight?: number | string;
    };
}

export interface NodeStyle {
    shape?: NodeShape;
    width?: number;
    height?: number;
    backgroundColor?: string;
    borderColor?: string;
    borderWidth?: number;
    textColor?: string;
    ports?: PortPosition[];
}

