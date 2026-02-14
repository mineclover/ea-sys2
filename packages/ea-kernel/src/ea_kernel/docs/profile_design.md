# Profile Design Principles

커널 프로파일 설계 원칙. ArchiMate 3.2, TOGAF 10, Zachman 6.0, SysML 2.0, BPMN 2.0 매핑 경험에서 도출.

## 2-Stage Validation

프로파일 검증은 2단계 파이프라인:

```
Stage 1: Profile rules — 도메인 수준 제약 (카테고리/레이어 패턴 매칭)
Stage 2: Kernel rules — 구조적 불변식 (엔티티 계층 매칭)
```

프로파일은 커널 규칙 위에 제약만 추가할 수 있고, 완화할 수 없다.

### 패턴 매칭 규약

| 패턴 | 대상 | 예시 |
|------|------|------|
| `@Category` | element.category | `@Behavior`, `@ActiveStructure` |
| `#Layer` | element.layer | `#Business`, `#Technology` |
| `ElementName` | element.name (정확 일치) | `BusinessProcess` |
| `*` | 모든 요소 | wildcard |

### 우선순위 밴드

| Priority | 용도 |
|----------|------|
| 1 | deny-by-default fallback (관계당 1개) |
| 40 | 넓은 카테고리 수준 허용 |
| 50 | 구체적 카테고리/교차 허용 |
| 60 | 교차 카테고리 허용 |
| 80 | 명시적 금지 (허용 규칙 오버라이드) |

### Fallback 규칙

모든 프로파일 관계는 `*→* via relation, valid=False, priority=1` fallback을 가져야 한다.
명시적 허용 규칙에 매칭되지 않는 조합은 자동 거부된다.


## Kernel Type Coverage

### v1.1 → v1.9 검증 결과 (5-profile)

11개 concrete 커널 타입이 5개 프레임워크의 200개 요소를 완전 매핑:

| Kernel Type | 역할 | 사용 프레임워크 | 매핑 수 |
|-------------|------|:---:|---------|
| structure | 능동 구조 | 5/5 | 52 |
| step | 행위 | 5/5 | 48 |
| item | 수동 구조 | 5/5 | 33 |
| package | 컨테이너 | 5/5 | 17 |
| event | 이벤트 | 5/5 | 20 |
| expression | 평가/제약 | 4/5 | 15 |
| state | 목표/전략 | 4/5 | 13 |
| port | 인터페이스 | 4/5 | 10 |
| action | 실행 단위 | 4/5 | 11 |
| feature | 거버넌스/특성 | 4/5 | 10 |
| datatype | 값 타입 | 3/5 | 4 |

SysML 2.0은 최초로 11/11 커널 타입 + 13/13 커널 관계 완전 사용을 달성한 프로파일.

### 엔티티 계층과 프로파일 카테고리 매핑

```
element
├── namespace
│   ├── metatype                ← association, specialization 참여 가능
│   │   ├── feature             ← connector, feature_typing 참여 가능
│   │   │   ├── port            Interface 카테고리
│   │   │   ├── step            Behavior 카테고리
│   │   │   ├── action          Executable 카테고리
│   │   │   ├── event           Event 카테고리
│   │   │   └── expression      Assessment 카테고리
│   │   ├── classifier
│   │   │   ├── structure       ActiveStructure 카테고리
│   │   │   ├── item            PassiveStructure 카테고리
│   │   │   └── datatype        Meaning/Value 카테고리
│   │   └── state               Goal/Strategy 카테고리
│   └── package                 Composite 카테고리 ← metatype 밖!
```

`package`가 `metatype` 계층 밖에 있으므로 `association`에 직접 참여할 수 없다.
이는 의도된 설계이며, [Package Exposure Pattern](#package-exposure-pattern)으로 해결한다.


## Kernel Relation Coverage

### 사용 분포 (v1.9: 13/13 완전 활성화)

| 커널 관계 | Layer | 사용 프로파일 수 | 프로파일 관계 매핑 수 |
|-----------|:---:|:---:|---------|
| association | L2 | 4/4 | 22 |
| specialization | L2 | 4/4 | 8 |
| ownership | L2 | 4/4 | 4 |
| membership | L2 | 4/4 | 4 |
| succession | L3 | 4/4 | 5 |
| flow | L3 | 4/4 | 4 |
| **feature_typing** | **L2** | **1/4** | **1** |
| **connector** | **L2** | **1/4** | **1** |
| **redefinition** | **L2** | **1/4** | **1** |
| **subsetting** | **L2** | **1/4** | **1** |
| **interaction** | **L3** | **1/4** | **1** |
| **triggering** | **L3** | **1/4** | **1** |
| **guarding** | **L3** | **1/4** | **1** |

굵은 글씨 = SysML 2.0이 최초 활성화한 관계 (7개)

### association 과부하

`association`이 전체 프로파일 관계의 51%(21/41)를 흡수한다.

```
TOGAF: assignment, hosting, uses, provides, consumes, accesses,
       governs, constrains, influences, traces, association → 모두 kernel association

ArchiMate: Assignment, Serving, Access, Influence, Association → 모두 kernel association
```

**프로파일 관계 이름은 `ProfileValidationResult.relationship_name`에 보존**되므로,
쿼리/분석 계층에서 프로파일 관계 이름으로 필터링하면 의미적 구분이 가능하다.

```python
result = validator.validate("Principle", "BusinessProcess", "governs")
# result.relationship_name == "governs"  ← 보존됨
# result.kernel_rule_id == "assoc-01"    ← 커널에서는 association
```

단, 이 보상은 **검증 결과 추적 시**에만 동작하며, 커널 수준 그래프 쿼리에서는 구분할 수 없다.


## Package Exposure Pattern

### 문제

커널 계층에서 `package`는 `namespace → element` 경로에 위치하므로
`metatype` 계열의 `association`에 직접 참여할 수 없다:

```
Location(package) ──association──→ Capability(structure)
                    ↑ 커널: package는 metatype가 아님 → DENIED
```

### 해법

package가 소유한 port/feature를 노출점으로 선언하고, 외부 연결은 이 노출점을 통해 수행:

```
package ──ownership──→ port ──association──→ metatype*
         (own-01 ✅)          (assoc-01 ✅)
```

### 구체적 예시

```
Location(package) ──ownership──→ LocationAccess(port) ──association──→ Capability(structure)
                                 ^노출점 선언              ^커널 허용

ScopeNetwork(package) ──ownership──→ NetworkEndpoint(port) ──connector──→ NetworkEndpoint(port)
                                     ^노출점                              ^다른 package의 노출점
```

### 프로파일 적용

```python
# package-typed 요소
ProfileElement("Location", "package", "Data", "Composite",
               "Conceptual or physical place")

# 대응하는 노출점 (반드시 함께 정의)
ProfileElement("LocationPresence", "port", "Data", "Interface",
               "Access point for elements situated at a location")
```

### 프로파일 규칙

```python
# package → 노출점 소유
KernelValidityRule("tg-expose-01", "@Composite", "@Interface",
                   "decomposition", valid=True, priority=50,
                   notes="Composite exposes interface")

# 노출점 → 외부 연결
KernelValidityRule("tg-iface-01", "@Interface", "@ActiveStructure",
                   "hosting", valid=True, priority=50,
                   notes="Interface connects to active structure")
```

### 이점

| | 직접 연결 (hack) | Package Exposure Pattern |
|-|:---:|:---:|
| 커널 변경 | 필요 | 불필요 |
| 연결 의미 | package가 뭘 노출하는지 불명 | port 이름이 의미를 전달 |
| 추적 가능성 | package→target 1홉 | package→port→target 2홉, 경로 추적 가능 |
| 미사용 관계 활성화 | 없음 | connector 활성화 (6→7/13) |
| 커널 의미론 | 위반 (package≠metatype) | 준수 (port∈metatype) |

### 원칙

> 프로파일 작성 시 package-typed 요소에는 반드시 대응하는 port 요소를 함께 정의할 것.
> 외부 연결은 package가 아닌 노출된 port/feature를 통해 수행할 것.


## Hosted Flow Pattern

### 문제

커널의 `flow`는 `connector`(L2)의 자식이므로 `feature` 계통만 참여 가능하다.
`classifier` 계통(`structure`, `item`)은 flow에 직접 참여할 수 없다.

```
structure ──flow──→ item
              ↑ 커널: structure는 classifier, feature 아님 → DENIED
```

### 해법

structure가 소유한 step/port를 통해 item과 flow를 수행한다:

**Pattern A (Step-mediated)**: 행위 워크플로우
```
structure ──ownership──→ step ──flow──→ item    (produces)
item ──flow──→ step ──ownership──→ structure    (consumes)
```

**Pattern B (Port-mediated)**: 서비스 인터페이스
```
structure ──ownership──→ port ──flow──→ item    (output)
item ──flow──→ port ──ownership──→ structure    (input)
```

### 언제 사용하는가

- **Pattern A**: 실행 행위가 중요한 모델 (governance lifecycle, BPMN)
- **Pattern B**: 인터페이스 노출이 중요한 모델 (서비스, API)

### 이 패턴을 지원하는 커널 규칙

| 규칙 ID | 패턴 | 우선순위 |
|---------|------|---------|
| flow-01 | feature* → feature* | 40 |
| flow-02 | item → feature* | 50 |
| flow-03 | feature* → item | 50 |
| own-02 | metatype* → feature* | 60 |

### Profile relation direction

produces/consumes를 구분하려면 relation에 `direction`을 명시한다:

```toml
[[relations]]
name = "produces"
kernel_relation = "flow"
direction = "out"

[[relations]]
name = "consumes"
kernel_relation = "flow"
direction = "in"
```

- `"out"` = 생산 방향 (step → item)
- `"in"` = 소비 방향 (item → step)
- `""` = 방향 미지정

ProfileAuditor가 동일 kernel_relation에 매핑된 relation들의 direction 일관성을 검증한다.

### Builder 지원

`ProfileBuilder.hosted_flow()` 헬퍼로 패턴의 구조적 타당성을 빌드 타임에 검증할 수 있다:

```python
builder.hosted_flow(
    host_category="ActiveComponent",
    step_category="BehavioralStep",
    data_category="PassiveAsset",
    kernel=KERNEL_SPEC,
)
```

검증 항목:
1. host → step ownership 허용 여부 (커널 수준)
2. step → data flow 허용 여부 (produces)
3. data → step flow 허용 여부 (consumes)
4. produce/consume relation이 프로파일에 정의되어 있는지

### 원칙

> classifier-typed 요소(structure, item)가 데이터 흐름에 참여해야 할 때,
> 반드시 소유한 feature-typed 요소(step, port)를 중개자로 사용할 것.
