# KICEM Ontology Extension Hybrid Model

- 목적: 건설공사 공종별 T-Box 자동확장 및 검증
- 연구 출발점: 철근콘크리트 공종 OWL 2와 공통 작업유형
- 최종 산출물: 공종별 독립 OWL·TTL, 검증 보고서, WBS 근거표
- 릴리스: `tbox-v3.1.0`
- 브랜치: `release/tbox-multitrade-v3`
- 내부 상태: `INTERNAL_RELEASE_READY_EXTERNAL_REVIEW_PENDING`

## 1. 프로젝트 범위

- 확장 대상

  - 건축: 타일공사
  - 토목: 우수공
  - 소방: 유도등 설비공사

- T-Box 포함 대상

  - 클래스
  - 상·하위 클래스 관계
  - 주석 속성
  - 근거 출처와 조항
  - OWL 공리

- 제외 대상

  - 개별 현장의 위치·층·공구
  - 물량·단가·일정·기성실적
  - 명명 개체와 사실 assertion
  - A-Box 데이터

## 2. 모델 구성

- 입력

  - 철근콘크리트 기준 온톨로지에서 정규화한 공통 상위 작업유형
  - 공종별 기준 기반 WBS
  - 부모 정답이 제거된 확장 후보

- 자동 처리

  - 후보 클래스 정규화
  - 어휘·작업 생애주기 규칙 기반 직접 부모 예측
  - 공종 루트 및 공통 작업유형 연결
  - 독립 T-Box OWL·TTL 생성

- 검증

  - 후보 입력과 검증용 gold 분리
  - OWL 2 DL 프로파일 검사
  - HermiT 일관성·클래스 만족 가능성 검사
  - Turtle/RDF/XML 의미 동등성 검사
  - 순수 T-Box 검사
  - competency question 검사
  - 결함 주입 검사
  - 반복 실행 결정성 검사
  - 공식 근거 URL 접근성 검사

```text
공통 작업유형 + 기준 기반 WBS
               ↓
        부모 없는 후보 입력
               ↓
        직접 부모 자동 예측
               ↓
         OWL·TTL T-Box 생성
               ↓
  구조·추론·근거·결정성 검증
```

## 3. 공종별 규모

| 공종 | 근거 | 확장 후보 | 공종별 클래스 수 |
|---|---|---:|---:|
| 건축-타일공사 | KCS 41 48 01 | 24 | 30 |
| 토목-우수공 | KCS 11 40 25, KCS 11 40 15, KCS 11 20 25, KCS 12 20 10 | 12 | 18 |
| 소방-유도등 설비공사 | NFPC 303, NFTC 303, 소방시설 자체점검 고시 | 15 | 21 |
| 합계 | 8개 공식 출처 | 51 | 69 |

## 4. 개발·검증 환경

- 기준 파일: [`environment.yml`](environment.yml)
- 환경명: `kicem-tbox-validation`
- 외부 생성 API: 사용하지 않음
- GPU: 최종 T-Box 빌드·검증에 필요하지 않음

| 항목 | 고정 환경 |
|---|---|
| 운영체제 | Ubuntu 24.04.3 LTS, x86_64 |
| Python | 3.11 |
| Java | OpenJDK 17 |
| RDFLib | 7.0.0 |
| Owlready2 | 0.48 |
| NetworkX | 3.3 |
| pip-audit | 2.10.1 |
| OWL 검증 | OWLAPI, HermiT |

- 최초 연구·데모 개발 장비

  - CPU: AMD Ryzen 5 5600X, 6코어 12스레드
  - RAM: 16 GB
  - GPU: NVIDIA GeForce RTX 3090, 24 GiB
  - GPU 용도: 이전 하이브리드 실험 파이프라인
  - 최종 릴리스 재현: CPU 기반 가능

## 5. 빠른 실행

- 실행 위치: 저장소 루트
- 요구사항

  - Conda
  - Java 17
  - 공식 출처 접근성 검사용 인터넷 연결

```bash
conda env create -f environment.yml
conda activate kicem-tbox-validation
python final_tbox/release_multitrade.py --stress-cycles 10
```

- 기존 환경 동기화

```bash
conda env update -n kicem-tbox-validation -f environment.yml --prune
```

- 성공 조건

  - 파일: `final_tbox/reports/multitrade_release_gate.json`
  - 필드: `passed: true`
  - 내부 상태: `INTERNAL_RELEASE_READY_EXTERNAL_REVIEW_PENDING`

## 6. 검증 결과

- 검증일: 2026-11-10
- 공종: 3개
- 확장 후보: 51개
- 내부 개발 gold 일치: 51/51
- competency question: 51/51
- 결함 주입 검출: 312/312
- 냉간 독립 실행: 10회
- 산출물 해시: 10회 동일
- 공식 출처 접근성: 8/8
- 릴리스 게이트: 15/15
- OWL 2 DL·HermiT 검증: 통과
- 내부 릴리스 판정: 통과
- 외부 전문가 의미검증: 미완료

## 7. 주요 파일

```text
.
├── README.md
├── environment.yml
├── requirements-validation.txt
├── KO/OWL2/                         # 철근콘크리트 참조 기준 OWL 2
└── final_tbox/
    ├── README.md                    # 상세 실행·검증 설명
    ├── WBS.md                       # 사람이 읽는 우수공·유도등 WBS
    ├── WBS_EVIDENCE.md              # WBS별 공식 기준·조항 추적표
    ├── FINAL_REPORT.md              # 최종 검증 결과
    ├── RELEASE_CHECKLIST.md         # 배포 점검표
    ├── benchmarks/
    │   ├── multitrade_candidates.json  # 부모 정답 없는 빌드 입력
    │   └── multitrade_gold.json        # validator 전용 내부 gold
    ├── outputs/multitrade/          # 공종별 OWL·TTL·manifest
    ├── reports/                     # 기계 검증 보고서
    ├── tests/                       # 격리·변조·근거 회귀검사
    └── release_multitrade.py        # 전체 릴리스 실행점
```

- 사람용 WBS: [`final_tbox/WBS.md`](final_tbox/WBS.md)
- WBS 근거표: [`final_tbox/WBS_EVIDENCE.md`](final_tbox/WBS_EVIDENCE.md)
- 최종 보고서: [`final_tbox/FINAL_REPORT.md`](final_tbox/FINAL_REPORT.md)
- 배포 점검표: [`final_tbox/RELEASE_CHECKLIST.md`](final_tbox/RELEASE_CHECKLIST.md)
- 전문가 검토 절차: [`final_tbox/MULTITRADE_EXPERT_REVIEW_PROTOCOL.md`](final_tbox/MULTITRADE_EXPERT_REVIEW_PROTOCOL.md)

## 8. WBS 근거

- 건축-타일공사

  - KCS 41 48 01 「타일공사」

- 토목-우수공

  - KCS 11 40 25 「노면배수」
  - KCS 11 40 15 「배수관」
  - KCS 11 20 25 「되메우기 및 뒤채움」
  - KCS 12 20 10 「배수공사 측량」

- 소방-유도등 설비공사

  - NFPC 303 「유도등 및 유도표지의 화재안전성능기준」
  - NFTC 303 「유도등 및 유도표지의 화재안전기술기준」
  - 「소방시설 자체점검사항 등에 관한 고시」

## 9. 결과 해석 범위

- 내부 수치의 의미

  - 고정된 3공종 개발 벤치마크에 대한 적합도
  - 현재 코드·후보·산출물의 재현성과 구조적 유효성
  - 부모 정답이 없는 빌드 입력에 대한 결과
  - `KO/OWL2`는 연구 참조 기준이며 릴리스 builder의 직접 런타임 입력은 아님

- 내부 수치가 의미하지 않는 것

  - 보지 않은 제4공종의 일반화 정확도 100%
  - 독립 전문가 정확도 100%
  - 현장별 WBS·물량·일정의 자동 생성 완료
  - 법정 검토·설계 검토·감리 검토의 대체

- 남은 외부 게이트

  - 공종별 실무전문가의 클래스 적절성 판정
  - 직접 부모 관계 판정
  - 누락 개념 표본을 이용한 selection recall 평가
