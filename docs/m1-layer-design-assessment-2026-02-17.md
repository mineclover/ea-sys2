# M1 Layer Design Assessment (2026-02-17)

## Scope

- Target: `/schema/{layer}` M1 topology design quality
- Layers: `kernel`, `infra`, `needs`, `decision`, `governance`, `flow`
- Data source:
  - `GET /layers/{layer}/m2?lang=en` (profile mapping 확인)
  - `GET /profiles/{profile}/topology?lang=en`
  - `GET /profiles/{profile}/topology?lang=en&cross_layer=true`

## Validation: ea-sys profile mapping

- `kernel` -> `EASystem-Kernel`
- `infra` -> `EASystem-Infra`
- `needs` -> `EASystem-Needs`
- `decision` -> `EASystem-Decision`
- `governance` -> `EASystem-Governance`
- `flow` -> `EASystem-Flow`

결론: 현재 `/schema/*`의 M1은 `ea-sys` 계열 프로파일을 기준으로 조회되고 있다.

## Metrics

- `own_ratio`: 노드 중 자기 레이어 소속 비율
- `edges_per_node`: 노드 1개당 엣지 수 (복잡도 지표)
- `cross_ratio`: 전체 엣지 중 cross-layer 엣지 비율
- `top3_share`: 상위 3개 relation이 차지하는 비율 (관계 표현 집중도)

| Layer | Nodes | Edges | own_ratio | edges_per_node | cross_ratio | relation_kinds | top3_share |
|---|---:|---:|---:|---:|---:|---:|---:|
| kernel | 106 | 3304 | 0.755 | 31.17 | 0.332 | 10 | 0.655 |
| infra | 57 | 239 | 0.649 | 4.19 | 0.331 | 6 | 0.782 |
| needs | 86 | 340 | 0.744 | 3.95 | 0.221 | 9 | 0.853 |
| decision | 84 | 1558 | 0.702 | 18.55 | 0.230 | 10 | 0.651 |
| governance | 134 | 6285 | 0.791 | 46.90 | 0.389 | 9 | 0.537 |
| flow | 84 | 3617 | 0.679 | 43.06 | 0.403 | 8 | 0.681 |

## Layer-by-layer assessment

### kernel

- 강점: own ratio가 높고 relation 종류도 충분함.
- 리스크: `edges_per_node=31.17`로 매우 고밀도.
- 판단: 모델 의미는 적절하나 M1 직출력은 과포화.

### infra

- 강점: 전체 복잡도는 낮음 (`4.19`).
- 리스크: own ratio가 가장 낮은 편(`0.649`), cross-layer 비중은 비교적 큼.
- 판단: 운영 관점 모델로는 유효하나, 자기 레이어 응집도 보강 필요.

### needs

- 강점: 복잡도 낮고 own ratio 양호.
- 리스크: `top3_share=0.853`로 relation 표현이 특정 관계(`contains`, `constrains`)에 과집중.
- 판단: 구조는 안정적이나 의미 표현 다양성(행동/목표/실행 연결) 보강 필요.

### decision

- 강점: relation 분산이 비교적 양호.
- 리스크: `edges_per_node=18.55`로 중-고복잡.
- 판단: 유효하나 시각화용 추상 레이어(aggregation) 필요.

### governance

- 강점: own ratio 최고(`0.791`), relation 분산도 양호.
- 리스크: `edges_per_node=46.90`, `cross_ratio=0.389`로 과고밀도/횡단결합.
- 판단: 도메인 설계는 강하지만 raw M1 직시각화에는 부적합.

### flow

- 강점: flow 특성상 의존/생산/소비 축이 명확.
- 리스크: `edges_per_node=43.06`, `cross_ratio=0.403`로 매우 무거움.
- 판단: 현재 구조 그대로는 탐색성/응답성 모두 악화.

## Overall conclusion

- 설계 자체의 방향(레이어 고유성 + cross-layer 연결)은 전반적으로 유효하다.
- 다만 `governance`, `flow`, `kernel`, `decision`은 M1 raw topology를 그대로 렌더하기에 너무 조밀하다.
- 즉 문제의 본질은 "모델 부정합"보다는 "표현 계층(M1 view)의 추상화 부재"다.

## Priority recommendations

1. M1 기본 뷰를 raw edge가 아니라 relation-group edge로 전환.
2. 레이어별 M1 목표 밀도 가드레일 도입:
   - `edges_per_node <= 12`
   - `cross_ratio <= 0.35` (governance/flow는 예외 정책 필요)
3. needs의 relation taxonomy 확장:
   - `behavior -> goal`, `execution -> behavior` 계열 관계를 명시적으로 보강.
4. M1 API에 view_mode 표준 추가:
   - `raw` / `summary` / `focus(layer|relation|core)` 형태로 조회 분리.

