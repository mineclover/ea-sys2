# ea-kernel Roadmap — AI 친화적 의사결정 시스템

## 핵심 인사이트

**규칙은 절대적 검증기가 아니라 축적된 추론 재료다.**

현재 커널은 15×14×67 타입 수준 토폴로지 유효성 판정기로, "허용/금지"의 이진 판정을 수행한다.
그러나 비즈니스가 다양해질수록 이진 판정보다 **메타데이터가 풍부한 증거 기반 판단**이 필요하다.

- 규칙 A는 UML 2.5.1 §7.4에서 유래하고, 규칙 B는 ArchiMate 3.2 프로파일의 경험적 관찰이다
- 두 규칙이 동일 트리플에 대해 충돌하면, 출처·신뢰도·도메인을 비교해야 한다
- AI 에이전트는 "왜 금지인가"를 물을 수 있어야 하고, "이 override는 합리적인가"를 판단할 수 있어야 한다

이를 위해 커널의 규칙을 **코퍼스(corpus)**로 격상시키고, 판정을 **증거 기반 판단(judgment)**으로 발전시킨다.

---

## 전체 로드맵

| Phase | 이름 | 추가하는 것 | 가능해지는 것 | 코퍼스 연결 | 상태 |
|-------|------|-----------|------------|-----------|------|
| 0 | Topology Validator | 81 rules, 5 profiles | 이진 유효성 판정 | — | **완료** |
| 0.5 | Rule Corpus Model | 메타데이터 + 코퍼스 쿼리 + judge | 증거 기반 판단, 도메인 간 충돌 감지 | 코퍼스 생성 | **완료** |
| 0.5→2.0 | 구조 변경 (15×14) | transition 관계, execution_mode/join_mode | 상태 전이, 병렬 실행, 복합 조건 | trans-01 코퍼스 엔트리 | **완료** |
| 1 | ~~FeatureSpec~~ | ~~타입의 feature 구성 선언~~ | ~~AI가 엔티티 내용 이해~~ | — | **제거** (커널 토폴로지 범위 밖) |
| 2 | Topology Navigation | 그래프 탐색 + 경로 열거 | AI가 흐름 탐색, 영향 분석 | 각 edge에 JudgmentReport | **완료** (v2.2.0) |
| 3 | Instance + Decision Recording | M0 적합성 + 의사결정 기록 | 결정 추적, override→학습 | 기록된 결정→empirical 엔트리 | **완료** (v2.3.0) |
| 4 | AI Decision Interface | 구조화된 컨텍스트 + 추천 | AI 에이전트 직접 상호작용 | 전체 코퍼스 활용 | **완료** (v2.4.0) |
| 4.5 | Performance Optimization | 내부 인덱스 + 캐시 + mutable 전환 | O(1) lookup, judge 최적화 | — | **완료** (v2.5.0) |

---

## Phase 0: Topology Validator (현재)

현재 커널의 상태.

- **KernelValidityRule**: id, source_pattern, target_pattern, relationship_name, valid, priority, conditions, notes
- **메타데이터 없음**: 규칙의 출처, 신뢰도, 도메인, 분류가 기록되지 않음
- **이진 판정**: `validate_relationship()` → `True/False`
- **Priority 기반 해소**: 충돌 시 높은 priority 승리, 동일 priority면 deny-first

---

## Phase 0.5: Rule Corpus Model (구현 완료)

### 목표

기존 `validate_relationship()`은 무변경으로 유지하면서, 병렬 경로로 **증거 기반 판단**을 제공한다.

### 구현 결과

**변경 파일 6개, 기존 코드 무변경, 51개 신규 테스트 전체 통과 (805 passed).**

#### 1. 새 타입 (`types.py` 끝에 추가)

| 타입 | 종류 | 용도 |
|------|------|------|
| `RuleCategory` | Enum | 규칙 분류 (structural / behavioral / domain / empirical) |
| `RuleConfidence` | Enum | 신뢰 수준 (universal / common / contextual / empirical) |
| `RuleMetadata` | frozen dataclass | 규칙 메타데이터 (domain, tags, category, confidence, source, rationale) |
| `RuleCorpusEntry` | frozen dataclass | rule + metadata 결합 — 코퍼스 기본 단위 |
| `RuleEvidence` | frozen dataclass | 판단 시 개별 규칙의 증거 (matched, is_winner, condition_results) |
| `JudgmentReport` | frozen dataclass | 증거 기반 판단 보고서 (verdict, evidence, confidence, domains, conflicts) |

#### 2. 메타데이터 파싱 (`spec_loader.py` 확장)

- `_parse_metadata(rule_id, data)` — TOML `[rules.xxx.metadata]` 서브테이블 파싱
- `load_kernel_rules_with_metadata()` → `(rules, constraints, metadata_map)` 반환
- 기존 `_parse_rule()`, `load_kernel_rules()` **무변경**

#### 3. `rule_corpus.py` (신규 모듈, 핵심)

```python
class RuleCorpus:
    # 팩토리
    @classmethod
    def from_kernel_spec(cls, schema, metadata_map=None) -> RuleCorpus

    # 메타데이터 추론 (L2→structural, L3→behavioral, deny+high→universal)
    @staticmethod
    def infer_metadata(rule) -> RuleMetadata

    # 불변 확장 — 프로파일 규칙 추가 시 새 코퍼스 반환
    def with_profile_rules(self, profile_name, rules, metadata_map=None) -> RuleCorpus

    # 쿼리
    def by_domain(self, domain) -> tuple[RuleCorpusEntry, ...]
    def by_tag(self, tag) -> tuple[RuleCorpusEntry, ...]
    def by_category(self, category) -> tuple[RuleCorpusEntry, ...]
    def by_confidence(self, confidence) -> tuple[RuleCorpusEntry, ...]

    # 교차 도메인 충돌 감지 (도메인별 winner verdict 비교)
    def detect_conflicts(self, source, target, relation) -> tuple[str, ...]

    # 증거 기반 판단 (validate_relationship()과 동일 verdict + 풍부한 증거)
    def judge(self, source, target, relation) -> JudgmentReport
```

#### 4. `profile_builder.py` 확장

- `allow()`, `deny()`에 `metadata: RuleMetadata | None = None` 파라미터 추가
- `build_with_corpus()` → `(KernelProfile, tuple[RuleCorpusEntry, ...])` 반환
- 기존 `build()` **무변경**

#### 5. TOML 메타데이터 (5개 대표 규칙)

`kernel_rules.toml`에 `[rules.xxx.metadata]` 서브테이블로 명시 메타데이터 추가:
- `mem-01` (structural/universal) — UML 2.5.1 §7.4
- `spec-01` (structural/universal) — UML 2.5.1 §9.9
- `flow-01` (behavioral/common) — KerML §8.4
- `succ-01` (behavioral/common) — KerML §8.3
- `assoc-01` (structural/common) — UML 2.5.1 §11.5

나머지 규칙은 `infer_metadata()`로 자동 추론.

### 하위 호환성

- **KernelValidityRule 무변경** — 기존 타입에 필드를 추가하지 않음
- 메타데이터는 `RuleCorpusEntry` 래퍼로 부착 — 기존 코드가 RuleCorpusEntry를 모르면 영향 없음
- `validate_relationship()`은 그대로 — `judge()`는 병렬 경로
- TOML의 `[rules.xxx.metadata]`는 기존 `_parse_rule()`이 자동 무시 (알려진 필드만 추출)

### 메타데이터 추론 로직

| 조건 | category | confidence |
|------|----------|------------|
| L2 관계 (membership~subsetting) | STRUCTURAL | — |
| L3 관계 (flow~guarding) | BEHAVIORAL | — |
| 그 외 | DOMAIN | — |
| deny + priority ≥ 80 | — | UNIVERSAL |
| deny + priority = 1 (fallback) | — | UNIVERSAL |
| 그 외 | — | COMMON |

---

## Phase 1: FeatureSpec (제거됨)

**제거 사유**: Feature composition/typing 제약은 커널 토폴로지와 직교하는 관심사다. 커널의 설계 철학은 "기능 구현의 복잡성을 제거하고 비즈니스 의사결정을 위한 진입점만 노출"하는 것이며, FeatureSpec은 이 원칙에 위배된다. Feature의 내부 구성 제약은 소비자 레이어의 책임이다.

---

## Phase 2: Topology Navigation

그래프 탐색과 경로 열거를 지원한다.

- **목적**: AI가 "A에서 B까지의 흐름 경로"를 탐색, 영향 분석 수행
- **설계**: 인접 리스트 기반 그래프 뷰, BFS/DFS 경로 열거, 관계 타입 필터
- **코퍼스 연결**: 각 edge(관계)에 `JudgmentReport`를 부착 — 탐색 중 "이 연결은 왜 허용되는가"를 증거와 함께 확인

---

## Phase 3: Instance + Decision Recording

M0 인스턴스 적합성 검증과 의사결정 기록을 지원한다.

- **목적**: 실제 데이터에 대한 커널 적합성 확인 + 인간의 override 결정을 기록
- **설계**: 인스턴스 검증 (M0→M2 적합성), DecisionRecord 타입 (who, when, what, why, override)
- **코퍼스 연결**: 기록된 결정이 empirical 코퍼스 엔트리로 환류 — override가 반복되면 새 규칙 후보

---

## Phase 4: AI Decision Interface

AI 에이전트가 커널과 직접 상호작용하는 구조화된 인터페이스를 제공한다.

- **목적**: AI가 "이 관계를 추가해도 되는가?"를 코퍼스 증거와 함께 판단
- **설계**: 구조화된 컨텍스트 API (현재 상태 + 관련 규칙 + 과거 결정), 추천 API (가능한 관계 열거 + 순위)
- **코퍼스 연결**: 전체 코퍼스 활용 — kernel + profile + empirical 규칙을 종합한 판단

---

## 피드백 루프

```
코퍼스 → AI 추론 → 의사결정 → 기록 → 새 코퍼스 엔트리
                                        ↑
                             (override → empirical rule)
                             (패턴 반복 → confidence 승격)
```

### Confidence 승격 경로

| 현재 수준 | 승격 조건 | 승격 대상 |
|----------|----------|----------|
| EMPIRICAL | 3회 이상 일관된 결정 | CONTEXTUAL |
| CONTEXTUAL | 10회 이상, 다수 도메인 | COMMON |
| COMMON | 인간 전문가 검토 + 승인 | UNIVERSAL |

UNIVERSAL로의 승격은 자동화하지 않는다. 타입 이론적 자명성은 인간이 확인해야 한다.

### 학습 사이클

1. AI가 `judge()`로 증거 기반 판단을 받음
2. 인간이 판단을 수용하거나 override
3. Override는 `DecisionRecord`로 기록 (Phase 3)
4. 반복된 override 패턴이 감지되면 `EMPIRICAL` 엔트리 자동 생성
5. 일관된 패턴이 축적되면 confidence 승격
6. 승격된 규칙이 다음 판단에 반영

---

## 설계 원칙

1. **하위 호환 최우선** — 각 Phase는 기존 API를 깨지 않는다. 새 기능은 병렬 경로로 추가.
2. **타입 안전** — 모든 새 타입은 frozen dataclass. 런타임 변이 없음.
3. **코퍼스 중심** — Phase 0.5 이후 모든 기능은 코퍼스를 통해 연결된다.
4. **AI 친화적** — 판단의 근거가 항상 구조화된 데이터로 제공된다.
5. **인간 최종 결정** — AI는 증거를 제시하고 추천하지만, 최종 결정은 인간이 한다.
