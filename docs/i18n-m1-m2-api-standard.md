# M1/M2 번역 및 번역 API 표준 가이드

## 1. 목적

`/explorer/kernel-schema` 및 레이어 스키마/토폴로지 화면에서 사용하는 번역 데이터를
일관된 방식으로 제공하기 위해, M2/M1 번역 데이터와 API 요청 규약을 표준화한다.

## 2. 적용 범위

- M2(커널 메타모델): `ea_kernel/specs/kernel_schema.toml` + `kernel_schema.{lang}.toml`
- M1(프로파일 메타모델): `ea_kernel/profiles/**/*.toml` + `{profile}.{lang}.patch.toml`
- API:
  - `GET /kernel/entities`
  - `GET /kernel/relations`
  - `GET /profiles/{name}`
  - `GET /profiles/{name}/topology`
  - `GET /layers/{layer_key}/m2`
  - `GET /governance/business-flow`

## 3. 번역 데이터 표준

### 3.1 공통 i18n 타입

- 번역 필드 타입은 `I18nString = string | Record<string, string>` 를 사용한다.
- 표준 번역 필드명:
  - `display_name`
  - `description`

### 3.2 M2 번역 패치 규칙

- 파일명: `kernel_schema.{lang}.toml`
- 섹션:
  - `[entities.<name>]`
  - `[relations.<name>]`
- 권장 필드:
  - `display_name`
  - `description`
  - `_en_display_name`, `_en_description` (stale audit 용)

예시:

```toml
[entities.element]
_en_display_name = "Element"
display_name = "요소"
description = "모든 커널 요소의 루트"
```

### 3.3 M1 번역 패치 규칙

- 파일명: `{profile_name_lower}.{lang}.patch.toml`
- 섹션:
  - `[elements.<name>]`
  - `[relations.<name>]`
  - `[validity_rules.<rule_id>]`
- relation 번역은 반드시 중첩 섹션을 사용한다.
  - 허용: `[relations.contains] display_name = "포함"`
  - 비권장/금지: `[relations] contains = "포함"`

예시:

```toml
[elements.KernelLayer]
display_name = "커널 계층"

[relations.contains]
display_name = "포함"
```

### 3.4 식별체계(언어 패치/감사용) 단일 규약

- 번역 슬롯의 표준 식별 튜플:
  - `(scope, profile, kind, name, field, lang)`
- 필드 의미:
  - `scope`: `m2` | `m1`
  - `profile`: M2는 `null`, M1은 레지스트리 프로파일명(예: `EASystem-Kernel`)
  - `kind`:
    - M2: `entity` | `relation`
    - M1: `element` | `relation` | `validity_rule`
  - `name`: 스키마/프로파일의 원본 식별자(대소문자 포함)
  - `field`: `display_name` | `description` (`validity_rule`는 `description`만 허용)
  - `lang`: 요청 언어 코드(예: `ko`)
- canonical identifier 문자열:
  - M2: `m2:{kind}:{name}:{field}`
  - M1: `m1:{profile}:{kind}:{name}:{field}`
- 패치 파일 섹션과 식별자 매핑:
  - `[entities.<name>]` ↔ `(m2, null, entity, <name>, <field>)`
  - `[relations.<name>]` ↔ `(m2, null, relation, <name>, <field>)`
  - `[elements.<name>]` ↔ `(m1, <profile>, element, <name>, <field>)`
  - `[relations.<name>]` ↔ `(m1, <profile>, relation, <name>, <field>)`
  - `[validity_rules.<rule_id>]` ↔ `(m1, <profile>, validity_rule, <rule_id>, description)`

### 3.5 객체 식별자 vs 번역 슬롯 식별자

- 번역 슬롯 식별자(3.4)는 패치/감사 대상 슬롯을 식별하기 위한 규약이다.
- API payload 객체 식별자는 별도 규약을 사용한다.
  - element: `m2::{layer_key}::element::{name}`
  - relation: `m2::{layer_key}::relation::{name}`
  - category: `m2::{layer_key}::category::{name}`
  - rule: `m2::{layer_key}::rule::{sha1(source|relation|target|valid|priority)[:12]}`
- 즉, 패치/감사 식별자는 `:` 기반, 객체 식별자는 `::` 기반으로 구분한다.

## 4. API 요청 표준

### 4.1 공통 쿼리 파라미터

- `lang` (optional):
  - 대상 언어 코드 (`ko`, `ja`, `en` 등)
  - 미지정 또는 `en`이면 기본 영문 기준 응답
  - 레이어 스키마 API는 `lang`만 사용한다 (`locale` 비사용)

### 4.2 레이어 M2 조회 엔드포인트 표준

- canonical endpoint: `GET /layers/{layer_key}/m2`
- 호환 alias: `GET /layers/{layer_key}/schema` (legacy client 호환용)
- 신규 클라이언트/문서/SDK는 반드시 `/m2`를 사용한다.
- 주요 응답 필드:
  - `identifier_system`: 식별 계산 계약(문자열 템플릿, rule 해시 규칙, kernel layer 매핑식, profile-rule binding 규칙)
  - `elements_by_layer`, `relations`, `rules`: 원본 M2 정의
    - `rules`는 `profile_name`, `profile_layer_key`, `profile_rule_id`, `profile_rule_identifier`를 포함해야 한다.
  - `m2_blueprint`: 카테고리 집약 그래프(`categories`, `relations`, `rules`, `layer_responsibilities`)
    - `m2_blueprint.rules`는 집약 edge가 참조하는 `profile_rule_ids` 샘플을 포함해야 한다.

예시(요약):

```json
{
  "layer_key": "needs",
  "identifier_system": {
    "profile_name": "EASystem-Needs",
    "namespace": "m2",
    "object_identifiers": {
      "element": "m2::needs::element::{element_name}",
      "relation": "m2::needs::relation::{relation_name}",
      "category": "m2::needs::category::{category_name}"
    },
    "rule_identifier": {
      "pattern": "m2::needs::rule::{digest12}",
      "digest_algorithm": "sha1",
      "digest_length": 12,
      "input_template": "{source}|{relation}|{target}|{valid_int}|{priority_int}"
    },
    "profile_rule_binding": {
      "profile_rule_identifier_pattern": "m1::EASystem-Needs::rule::{rule_id}",
      "binding_fields": ["profile_name", "profile_layer_key", "profile_rule_id"]
    }
  },
  "m2_blueprint": {
    "summary": { "category_count": 11, "relation_count": 10, "rule_edge_count": 43 },
    "layer_responsibilities": [
      { "layer": "L1", "role": "..." },
      { "layer": "L2", "role": "..." },
      { "layer": "L3", "role": "..." },
      { "layer": "L4", "role": "..." }
    ]
  }
}
```

### 4.3 M1 Topology 조회 표준

- endpoint: `GET /profiles/{name}/topology`
- 쿼리 파라미터:
  - `lang` (optional): `en|ko|...` (기본 `en`)
  - `cross_layer` (optional): `true|false` (기본 `false`)
  - `view_mode` (optional): `raw|summary|focus` (기본 `raw`)
  - `domain_scope` (optional): `all|owned|bridge` (기본 `all`, EA-sys 프로파일에서만 scope 적용)
  - `max_edges` (optional): `>0` 정수
  - `focus` (optional, `view_mode=focus`일 때): `core|relation|layer|actor` (기본 `core`)
  - `focus_relation` (optional, `focus=relation`일 때 필수): relation 이름
  - `focus_layer` (optional, `focus=layer`일 때 필수): layer 이름 (`Infra|Governance|Decision|Needs|Kernel|Flow`)
  - `focus_actor` (optional, `focus=actor`일 때 seed actor 이름)
  - `focus_depth` (optional, `focus=actor`일 때 BFS depth, 기본 4)
- `view_mode=summary` 의미:
  - edge를 `(source, target, relation)` 키로 집약한다.
  - 집약 edge는 `rule_count`(원본 edge 수), `priority`(최대 priority), `edge_origin`(`explicit|expanded|mixed`)를 포함한다.
  - origin 분포는 `explicit_count`, `expanded_count`로 제공한다.
  - node 집약은 하지 않으며, node set은 프로파일 원본을 유지한다.
- `view_mode=focus` 의미:
  - `focus=core`: 고정 표층 규칙(구조/인과)으로 edge를 집약한다.
    - visible: `contains`, `depends_on`, `next`, `triggers`, `constrains`
    - hidden(default): `produces`, `consumes`, `coordinates`, `registers`, `available_in`, `specialization`, `redefinition`, `subsetting`, `feature_typing`
  - `focus=relation`: 지정 relation만 edge를 집약한다.
  - `focus=layer`: 지정 layer에 접한 edge만 집약한다.
  - `focus=actor`: actor seed를 기준으로 유효 상호작용 관계를 집약한다.
  - 응답 `focus` 필드에 적용 모드와 후보 집합(`relation_candidates`, `layer_candidates`), 시각화 정책(`visibility_profile`, `visible_relations`, `hidden_relations`)을 포함한다.
- 응답 메타 필드:
  - `view_mode`
  - `edge_total_raw` (view_mode 적용 전 edge 수)
  - `edge_total_before_cap` (`max_edges` cap 적용 전 edge 수)
  - `edge_truncated` (`max_edges`로 잘렸는지 여부)
  - `domain_view` (`profile_layer_key`, `scope`, `stats`)
- edge origin 표준:
  - raw edge는 `edge_origin`(`explicit|expanded`)를 포함해야 한다.
  - summary/focus edge는 `edge_origin`(`explicit|expanded|mixed`)과 `explicit_count`, `expanded_count`를 포함해야 한다.
- semantic 노출 표준:
  - 모든 edge는 `semantic_axis`, `semantic_intent`, `surface_exposed`를 포함해야 한다.
  - 응답 루트는 `semantic_view.axis_distribution`, `semantic_view.intent_distribution`, `semantic_view.surface_edges`를 포함해야 한다.
  - `semantic_view.profile_scope`는 semantic profile 출처(`global` 또는 `layer:{layer_key}`)를 나타낸다.
  - 레이어별 의미 프로파일 override 예:
    - `infra`: `registers -> integration/adapter_binding`, `produces -> persistence/write`, `consumes -> persistence/read`
    - `needs`: `constrains -> intent/priority_alignment`, `next -> journey/journey_step`
    - `kernel`: `constrains -> invariant/invariant_enforcement`, `registers -> contract/contract_binding`

### 4.3.1 M1 Projection 조회 표준 (M1P)

- endpoint: `GET /profiles/{name}/projection`
- 목적:
  - M1 raw를 직접 렌더링하지 않고, 탐색 목적별 추상화 레벨(L0~L4)로 투영한다.
- 쿼리 파라미터:
  - `level`: `l0|l1|l2|l3|l4` (기본 `l0`)
  - `lens`: `panorama|overview|capability|interaction|execution|trace`
  - `cross_layer`: `true|false` (기본 `false`)
  - `domain_scope`: `all|owned|bridge` (기본 `all`)
  - `lang`: i18n 언어
  - `actor`, `depth`: `l2(interaction)` actor seed와 깊이 제어
  - `max_edges`: projection budget override
- 응답 필드:
  - topology 기본 필드(`nodes`, `edges`, `relation_distribution`, ...)
  - `projection` 메타:
    - `level`, `lens`, `description`
    - `budget.default_max_edges`, `budget.effective_max_edges`
    - `filters.relations`, `filters.categories`, `filters.domain_scope`
    - `drilldown.next_levels`
    - `source` (projection 생성에 사용한 원본 view)
    - `seed` (actor 기반 렌즈일 때)

### 4.3.2 M1 Composed 조회 표준 (Cross-Profile)

- endpoint: `GET /profiles/{name}/composed`
- 목적:
  - 단일 프로파일 M1이 아니라, anchor 프로파일을 기준으로 여러 프로파일을 합성한 M1을 조회한다.
  - 규칙 귀속(rule ownership)을 edge 단위로 유지해 다중 도메인 설계를 추적한다.
- 쿼리 파라미터:
  - `lang`: i18n 언어
  - `domain_scope`: `all|owned|bridge` (기본 `all`)
  - `max_edges`: edge cap
  - `include_profiles`: 쉼표 구분 프로파일 목록 (미지정 시 EA-sys 표준 세트를 anchor 기준으로 자동 선택)
  - `focus` (optional): `core|relation|layer|actor`
  - `focus_relation` (optional, `focus=relation`일 때 필수)
  - `focus_layer` (optional, `focus=layer`일 때 필수)
  - `focus_actor`, `focus_depth` (optional, `focus=actor`일 때 seed/depth)
- 응답 필드:
  - topology 기본 필드(`nodes`, `edges`, `relation_distribution`, ...)
  - `view_mode`: `summary` 또는 `focus`
  - `focus`: focus 모드/후보/선택 관계 정보
  - `nodes[].profile_owners[]`: 해당 node를 소유/정의하는 프로파일 목록
  - `edges[].edge_origin`, `edges[].explicit_count`, `edges[].expanded_count`: 합성 edge의 명시/확장 성질
  - `composition` 메타:
    - `mode` (`cross_profile`)
    - `anchor_profile`, `anchor_layer_key`
    - `included_profiles`, `requested_profiles`, `missing_profiles`
    - `source_profile_count`

### 4.4 감사(Audit) API 표준

- M2 감사: `GET /i18n/audit?lang={lang}`
- M1 감사: `GET /i18n/audit/profiles/{name}?lang={lang}`
- 감사 응답의 이슈 항목(`missing`, `orphan`, `stale`)은 아래 공통 필드를 포함:
  - `kind`, `name`, `field`, `identifier`
  - M1 감사는 추가로 `profile` 필드 포함

### 4.5 Needs 목적값 표준 (M2 Goal 정합)

- 대상 엔드포인트: `POST /needs/catalogs/{catalog_id}/needs`
- `purpose`는 free-text가 아니라 표준 taxonomy 값만 허용한다.
- canonical 값:
  - `safety`
  - `efficiency`
  - `usability`
  - `compliance`
  - `growth`
  - `trust`
  - `unspecified`
- 호환 입력:
  - `NeedPurposeSafety` 같은 M2 element 스타일 이름은 수용 후 canonical 값으로 정규화한다.
- 응답의 `purpose`는 항상 canonical 값으로 반환한다.

### 4.6 Needs 우선순위/표현력 표준

- 대상 엔드포인트:
  - `POST /needs/catalogs/{catalog_id}/needs`
  - `POST /needs/catalogs/{catalog_id}/needs/{need_id}/revise`
- `priority`는 canonical 값만 허용한다.
  - `critical | high | medium | low`
- 호환 입력:
  - `NeedPriorityHigh` 같은 M2 element 스타일 이름은 수용 후 canonical 값으로 정규화한다.
- `GET /needs/catalogs/{catalog_id}/needs`는 아래 필드를 기본 포함해야 한다.
  - `purpose`, `cause_types`, `complexity`, `use_case_id`
- `GET /needs/catalogs/{catalog_id}/needs`는 아래 필터를 지원해야 한다.
  - `status`, `priority`, `stakeholder_id`, `purpose`, `complexity`, `use_case_id`, `cause_type`

### 4.7 Needs Write API 표준 (Catalog 모델링)

- use-case 추가:
  - `POST /needs/catalogs/{catalog_id}/use-cases`
- need revision:
  - `POST /needs/catalogs/{catalog_id}/needs/{need_id}/revise`
- process unit 추가:
  - `POST /needs/catalogs/{catalog_id}/needs/{need_id}/process-units`
- decision evidence 상속:
  - `POST /needs/catalogs/{catalog_id}/needs/{need_id}/inherit-decision-evidence`

## 5. 사용 예시

### 5.1 커널 M2를 한국어로 조회

```bash
curl "http://localhost:9000/kernel/entities?lang=ko"
```

### 5.2 M1 프로파일 토폴로지를 한국어로 조회

```bash
curl "http://localhost:9000/profiles/EASystem-Kernel/topology?lang=ko"
```

### 5.2.1 M1 토폴로지를 summary 모드로 조회

```bash
curl "http://localhost:9000/profiles/EASystem-Infra/topology?lang=ko&view_mode=summary&max_edges=1200"
```

### 5.3 레이어 M2 스키마를 한국어로 조회

```bash
curl "http://localhost:9000/layers/kernel/m2?lang=ko"
```

### 5.4 M1 프로파일 패치 감사 조회

```bash
curl "http://localhost:9000/i18n/audit/profiles/EASystem-Kernel?lang=ko"
```

### 5.5 Needs 목적 분류를 명시해 니즈 표현

```bash
curl -X POST "http://localhost:9000/needs/catalogs/{catalog_id}/needs" \
  -H "Content-Type: application/json" \
  -d '{
    "stakeholder_id": "sh-001",
    "action": "stabilize",
    "subject": "incident response",
    "purpose": "safety"
  }'
```

## 6. 구현 기준점

- 커널 서비스 적용: `packages/ea-kernel/src/ea_kernel/kernel_service.py`
- 거버넌스 서비스 적용: `packages/ea-governance/src/ea_governance/governance_service.py`
- API 라우터 적용:
  - `packages/ea-kernel/src/ea_kernel/api/server.py`
  - `packages/ea-governance/src/ea_governance/api_router.py`
