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
  - `GET /layers/{layer_key}/schema`
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

## 4. API 요청 표준

### 4.1 공통 쿼리 파라미터

- `lang` (optional):
  - 대상 언어 코드 (`ko`, `ja`, `en` 등)
  - 미지정 또는 `en`이면 기본 영문 기준 응답

### 4.2 감사(Audit) API 표준

- M2 감사: `GET /i18n/audit?lang={lang}`
- M1 감사: `GET /i18n/audit/profiles/{name}?lang={lang}`
- 감사 응답의 이슈 항목(`missing`, `orphan`, `stale`)은 아래 공통 필드를 포함:
  - `kind`, `name`, `field`, `identifier`
  - M1 감사는 추가로 `profile` 필드 포함

## 5. 사용 예시

### 5.1 커널 M2를 한국어로 조회

```bash
curl "http://localhost:9000/kernel/entities?lang=ko"
```

### 5.2 M1 프로파일 토폴로지를 한국어로 조회

```bash
curl "http://localhost:9000/profiles/EASystem-Kernel/topology?lang=ko"
```

### 5.3 레이어 M2 스키마를 한국어로 조회

```bash
curl "http://localhost:9000/layers/kernel/schema?lang=ko"
```

### 5.4 M1 프로파일 패치 감사 조회

```bash
curl "http://localhost:9000/i18n/audit/profiles/EASystem-Kernel?lang=ko"
```

## 6. 구현 기준점

- 커널 서비스 적용: `packages/ea-kernel/src/ea_kernel/kernel_service.py`
- 거버넌스 서비스 적용: `packages/ea-governance/src/ea_governance/governance_service.py`
- API 라우터 적용:
  - `packages/ea-kernel/src/ea_kernel/api/server.py`
  - `packages/ea-governance/src/ea_governance/api_router.py`
