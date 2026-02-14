# Process: 5-Phase Design Philosophy Authoring

## Phase 1: Benchmark Extraction

벤치마크 문서(ea-kernel CLAUDE.md)를 읽고 섹션 스키마를 추출한다.

1. 벤치마크 파일을 읽는다
2. 각 `##` 헤딩을 섹션으로 식별한다
3. 섹션마다 **slots**(채울 변수)와 **rules**(제약)를 기록한다
4. `references/meta-model.toml`과 대조하여 누락된 섹션이 없는지 확인한다

Output: 섹션 스키마 체크리스트

## Phase 2: Target Exploration

대상 패키지의 코드를 탐색하여 사실(fact)을 수집한다.

1. `src/{pkg}/` 아래 모든 `.py` 파일 목록을 확보한다
2. 각 파일의 주요 클래스/타입, `frozen` 여부, import 관계를 기록한다
3. 외부 패키지(ea-kernel 등) import 여부를 확인한다
4. 고아 모듈(어디서도 import되지 않는 파일)을 식별한다
5. 중복 정의(같은 개념의 다른 이름)를 식별한다

Output: 모듈별 팩트 시트

## Phase 3: Document Authoring

메타모델 슬롯을 팩트 시트로 채워 CLAUDE.md를 작성한다.

1. S1: 패키지 정체성·기반·의존성으로 one-liner 작성
2. S2: 코드에서 발견한 계층 구조를 Layer 모델로 정리, 핵심 원칙 한 줄 집약
3. S3: S2에서 분리된 복수 원칙을 Domain Principles로 배치
4. S4: 파일 트리 + Layer 태그. 미성숙이면 한계/목표 서브섹션 추가
5. S5-S6: 프로젝트 공통 컨벤션 적용
6. S7: 의존성 화살표 그래프 + 산문 3줄 + 금지 규칙

규칙:
- 핵심 원칙은 반드시 한 줄
- Module Structure의 모든 파일에 Layer 태그
- Dependency Direction 산문에 Kernel 동형성 언급

## Phase 4: Model-based Evaluation

작성된 문서를 메타모델에 매핑하여 평가한다.

1. `meta-model.toml`의 각 섹션을 순회한다
2. 문서에서 대응 섹션을 찾고 슬롯이 채워졌는지 확인한다
3. `[evaluation.criteria]`의 10개 기준으로 적합성 판정 (error/warning)
4. 벤치마크와 나란히 비교하여 톤·밀도·길이 일관성 확인
5. 차이가 있으면 **정당한 차이**(패키지 성숙도 등) vs **결함**으로 분류

Output: 속성별 적합성 테이블 (✅/⚠️/❌)

## Phase 5: Iteration

평가 결과의 error를 수정하고, warning을 정당화하거나 개선한다.

1. severity=error 항목은 반드시 수정
2. severity=warning 항목은 정당화 사유가 있으면 유지, 없으면 수정
3. 수정 후 Phase 4를 재실행하여 전체 통과 확인
4. 최종 결과를 사용자에게 요약 보고

Output: 수정된 CLAUDE.md + 평가 결과 요약
