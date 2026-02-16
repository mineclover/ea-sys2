# ea-kernel TODO — 완성도 향상 계획

> 현재 완성도: **~98%**. 핵심 기능 전수 구현·71개 테스트 파일·자기 검증 TOML 스펙 보유.
> 이 문서는 남은 갭을 분류하고 성공 기준을 정의한다.

---

## 1. 컨벤션 정렬 (Convention Alignment)

### 1.1 kernel_service.py keyword-only 인자 보정 ✅

**문제**: §3.2 위반. 공개 함수 14개가 positional 인자를 허용.

**성공 기준**:
- [x] 14개 함수 전부 `*` 적용
- [x] mcp_server.py 호출부 keyword 전환
- [x] __main__.py 호출부 keyword 전환
- [x] test_kernel_service.py 호출부 keyword 전환
- [x] `make test-kernel` 전체 통과 (1521 passed)

---

## 2. 문서 정합성 (Documentation Alignment)

### 2.1 CLAUDE.md 모듈 목록 갱신 ✅

**성공 기준**:
- [x] CLAUDE.md "Module Structure" 섹션에 15개 모듈 추가
- [x] Dependency Direction 섹션에 신규 모듈 간 의존 관계 반영
- [x] 기존 모듈 설명과 일관된 주석 형식

### 2.2 Kernel-Specific Patterns 섹션 보강 ✅

**성공 기준**:
- [x] 4개 패턴 추가 (6-Phase Governance Lifecycle, Store 3중 구현, Event Bus 패턴, What-If Simulation)
- [x] 각 패턴에 대응 모듈 명시

---

## 3. 코드 품질 (Code Quality)

### 3.1 notification_service.py 구체 구현 ✅

**성공 기준**:
- [x] `LoggingNotificationService` 구현 (logging 모듈 사용, 레벨 매핑 포함)
- [x] lifecycle_controller.py에서 실제 알림 발행 연결 (기존 연결 확인)
- [x] 테스트: Mock + Logging 둘 다 검증 (`test_notification_service.py`, 9 tests)

### 3.2 테스트 구조 개선 ✅

**성공 기준**:
- [x] `test_evidence_analyzer.py` 분리 (test_governance_phase2.py에서)
- [x] `test_judgment_service.py` 분리 (test_governance_phase4.py에서)
- [x] `test_impact_evaluator.py` 분리 (test_governance_phase4.py에서)
- [x] `test_what_if_simulator.py` 분리 (test_governance_phase3.py에서)
- [x] `test_promotion_engine.py` 분리 (test_governance_phase3.py에서)
- [x] `test_rule_asset_store.py` 분리 (test_governance_phase3.py에서)
- [x] `test_lifecycle_events.py` 분리 (test_governance_phase4.py에서)
- [x] `test_lifecycle_controller.py` 분리 (test_governance_phase5.py에서)
- [x] 기존 phase 테스트 파일은 E2E 통합 시나리오 테스트로 유지
- [x] `make test-kernel` 전체 통과 (1521 passed → 1530 passed)

---

## 4. 기능 완결 (Feature Completion)

### 4.1 자체 특화 스토어 (§5.4 방향) ✅

**성공 기준**:
- [x] 커널 스토어 vs 거버넌스 kernel_store 역할 분담 문서화 (CLAUDE.md Store 섹션에 경계 테이블 추가)
- [x] 프로파일 버전 히스토리 조회 서비스 함수 (`kernel_service.py`에 추가)

### 4.2 specs/ TOML 외부화 완결

**현재**: kernel_schema.toml + kernel_rules.toml + kernel_schema.ko.toml — 3파일.

**결정**: 거버넌스 상태 전이 규칙(VALID_TRANSITIONS)은 Python 인라인 유지. 이유:
- 전이 규칙이 5개 미만으로 단순
- TOML 외부화 대비 유지보수 이점 없음
- 런타임에 상태 머신 검증이 필요하므로 Python 코드와 결합이 자연스러움

**성공 기준**:
- [x] 거버넌스 상태 전이 규칙의 TOML 외부화 여부 결정 (인라인 유지로 결정)
- N/A 외부화 불필요

---

## 우선순위 및 실행 순서

| 순서 | 항목 | 상태 |
|:----:|------|:----:|
| 1 | 1.1 keyword-only 보정 | ✅ |
| 2 | 2.1 CLAUDE.md 모듈 목록 갱신 | ✅ |
| 3 | 2.2 Kernel-Specific Patterns 보강 | ✅ |
| 4 | 3.2 테스트 구조 개선 | ✅ |
| 5 | 3.1 notification_service 구현 | ✅ |
| 6 | 4.1 스토어 역할 경계 문서화 | ✅ |
| 7 | 4.2 거버넌스 전이 TOML 외부화 결정 | ✅ (인라인 유지) |

---

## 성공 기준 요약 (Definition of Done)

커널 완성도 **~98%** 선언 조건:

1. ✅ **컨벤션 100% 준수**: kernel_service.py 전 함수 keyword-only
2. ✅ **문서 정합**: CLAUDE.md 모듈 목록 = 실제 모듈 1:1 매칭
3. ✅ **테스트 가시성**: 주요 모듈별 전용 테스트 파일 존재 (8개 신규 파일)
4. ✅ **전체 테스트 통과**: `make test-kernel` green (1530 passed)
5. ✅ **스토어 경계 명확**: 커널 자체 스토어 vs 거버넌스 스토어 역할 문서화
6. ✅ **알림 구현**: LoggingNotificationService (logging 기반, 레벨 매핑)

### 잔여 항목
- ~~프로파일 버전 히스토리 조회 서비스 함수 (kernel_service.py)~~ ✅
