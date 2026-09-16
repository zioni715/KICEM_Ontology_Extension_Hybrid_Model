# RCPP OWL 2 검증 보고서

## 1. 검증 대상

- OWL 2 원본
  - `KO/OWL2/rcpp-owl-final.ttl`
- HermiT 추론 결과
  - `KO/OWL2/rcpp-owl-inferred.ttl`
- OWL 2 전용 SHACL
  - `KO/OWL2/owl2-shapes.ttl`
- 검증일
  - 2026-08-27

## 2. HermiT 검증

### 2.1 검증 환경

- 도구
  - Protégé Desktop
- Reasoner
  - HermiT Reasoner
- 입력 파일
  - `rcpp-owl-final.ttl`
- 검증 항목
  - OWL 2 온톨로지의 논리적 일관성
  - 클래스 및 속성 공리에 따른 추론
  - inferred ontology 생성 가능 여부

### 2.2 검증 결과

- 일관성 검사
  - 통과
- 논리적 비일관성
  - 없음
- 추론 실행
  - 완료
- inferred ontology 내보내기
  - 완료
- 결과 파일
  - `rcpp-owl-inferred.ttl`

### 2.3 추론 결과

- 추론으로 확인된 Functional Property
  - `calculatedUnitPrice`
  - `currentQuantity`
  - `expenseUnitCost`
  - `laborUnitCost`
  - `materialUnitCost`
- Functional Property 추론 수
  - 5개
- inferred 파일의 용도
  - HermiT가 도출한 추론 공리 보관
- 원본 대체 여부
  - 원본 대체 불가
  - `rcpp-owl-final.ttl`과 함께 사용

## 3. OWL 2 전용 SHACL 검증

### 3.1 검증 환경

- 검증 도구
  - pySHACL 0.40.0
- 데이터 그래프
  - `rcpp-owl-final.ttl`
- Shapes 그래프
  - `owl2-shapes.ttl`
- 추론 옵션
  - `inference="rdfs"`
- 실행 코드
  - `KO/OWL2/validate_owl2.py`

### 3.2 SHACL 구성

- 전체 트리플
  - 145개
- NodeShape
  - 6개
- 속성 경로 제약
  - 14개
- SPARQL 제약
  - 8개

### 3.3 검증 항목

- 온톨로지
  - 온톨로지 IRI 확인
  - `owl:Ontology` 선언 확인
- 클래스
  - Named Class 31개 확인
  - 클래스 IRI 확인
  - `rdfs:label` 확인
  - `rdfs:comment` 확인
- Object Property
  - 18개 확인
  - 속성 IRI 확인
  - `rdfs:label` 및 `rdfs:comment` 확인
  - domain 최대 1개 확인
  - range 정확히 1개 확인
  - domain·range의 OWL Class 유형 확인
- Datatype Property
  - 37개 확인
  - 속성 IRI 확인
  - `rdfs:label` 및 `rdfs:comment` 확인
  - domain 최대 1개 확인
  - range 정확히 1개 확인
  - XSD 데이터형 확인
- Restriction
  - 47개 확인
  - `owl:onProperty` 확인
  - Object Property 또는 Datatype Property 연결 확인
  - 역속성 표현 확인
  - 제약 술어 존재 여부 확인
  - qualified cardinality의 `owl:onClass` 또는 `owl:onDataRange` 확인
- Named Individual
  - 9개 확인
  - 개체 IRI 확인
  - `rdfs:label` 확인
  - 업무 클래스 유형 확인

### 3.4 SHACL 검증 결과

- SHACL 적합성
  - 통과
- 검출된 위반
  - 0건
- 최종 판정
  - OWL 2 구조 적합

## 4. 종합 결과

| 검증 | 도구 | 결과 |
|---|---|---|
| OWL 2 논리적 일관성 | HermiT Reasoner | 통과 |
| OWL 2 추론 | HermiT Reasoner | 통과 |
| inferred ontology 생성 | Protégé Desktop | 완료 |
| OWL 2 구조 검증 | OWL 2 전용 SHACL·pySHACL | 통과 |
| SHACL 위반 | pySHACL | 0건 |

## 5. 재현 방법

### 5.1 HermiT

- Protégé에서 `rcpp-owl-final.ttl` 열기
- `Reasoner → HermiT` 선택
- `Reasoner → Start reasoner` 실행
- 일관성 오류 확인
- inferred axioms를 `rcpp-owl-inferred.ttl`로 내보내기

### 5.2 SHACL

```bash
python KO/OWL2/validate_owl2.py
```

- 성공 출력
  - `[PASS] OWL 2 structural SHACL conforms: rcpp-owl-final.ttl`
  - `[OK] OWL 2 structural SHACL and inferred artifact check passed`

## 6. 검증 범위

- HermiT
  - OWL 2 논리적 일관성과 추론 검증
- OWL 2 전용 SHACL
  - OWL 2 문서의 구조와 필수 선언 검증
- 역할 구분
  - SHACL은 HermiT의 논리적 일관성 검사를 대체하지 않음
  - HermiT는 SHACL 구조 제약 검사를 대체하지 않음
