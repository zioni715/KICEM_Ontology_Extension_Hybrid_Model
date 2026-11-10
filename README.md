# 건설공사 T-Box 자동확장 모델

- 철근콘크리트 공종 온톨로지를 기준으로 다른 공종의 T-Box를 확장하는 프로젝트
- 확장 대상: 타일공사, 우수공, 유도등 설비공사
- 현재 버전: `tbox-v3.1.0`
- 작업 브랜치: `release/tbox-multitrade-v3`

## 적용 범위

- 생성 대상
  - 클래스
  - 직접 상위·하위 클래스 관계
  - 주석 속성
  - 출처와 근거 조항
  - OWL 공리
- 생성 제외
  - 현장·층·공구 등 개별 개체
  - 물량·단가·일정·기성실적
  - A-Box assertion

## 처리 흐름

```text
공통 작업유형 + 공종별 WBS
              ↓
      상위 클래스가 없는 후보
              ↓
       직접 상위 클래스 예측
              ↓
       공종별 OWL·TTL 생성
              ↓
      구조·추론·근거 검증
```

- 입력
  - 철근콘크리트 기준 온톨로지에서 정리한 공통 작업유형
  - 공종별 기준에 따라 작성한 WBS
  - 정답 상위 클래스가 제거된 확장 후보
- 처리
  - 클래스명 정규화
  - 어휘 및 작업 단계 규칙 적용
  - 직접 상위 클래스 예측
  - 공종 루트와 공통 작업유형 연결
  - 공종별 독립 T-Box 생성

## 공종별 데이터

| 공종 | 주요 근거 | 확장 후보 | 생성 클래스 |
|---|---|---:|---:|
| 타일공사 | KCS 41 48 01 | 24 | 30 |
| 우수공 | KCS 11 40 25, KCS 11 40 15, KCS 11 20 25, KCS 12 20 10 | 12 | 18 |
| 유도등 설비공사 | NFPC 303, NFTC 303, 소방시설 자체점검 고시 | 15 | 21 |
| 합계 | 공식 출처 8건 | 51 | 69 |

## 실행 환경

- 운영체제: Ubuntu 24.04.3 LTS, x86_64
- Python: 3.11
- Java: OpenJDK 17
- RDFLib: 7.0.0
- Owlready2: 0.48
- NetworkX: 3.3
- OWL 검증: OWLAPI, HermiT
- 환경 정의: [`environment.yml`](environment.yml)
- GPU: 필요 없음

최초 실험 장비:

- CPU: AMD Ryzen 5 5600X
- RAM: 16 GB
- GPU: NVIDIA GeForce RTX 3090 24 GiB
- 최종 T-Box 생성 및 검증: CPU만으로 실행 가능

## 실행 방법

요구사항:

- Conda
- Java 17
- 공식 출처 URL 확인을 위한 인터넷 연결

```bash
conda env create -f environment.yml
conda activate kicem-tbox-validation
python final_tbox/release_multitrade.py --stress-cycles 10
```

기존 환경 갱신:

```bash
conda env update -n kicem-tbox-validation -f environment.yml --prune
```

실행 결과 확인:

- 보고서: `final_tbox/reports/multitrade_release_gate.json`
- 통과 조건: `passed: true`

## 검증 항목

- 후보 입력과 검증용 gold 분리
- OWL 2 DL 프로파일 검사
- HermiT 일관성 및 클래스 만족 가능성 검사
- RDF/XML과 Turtle 의미 동등성 검사
- A-Box 혼입 검사
- competency question 검사
- 결함 주입 검사
- 반복 실행 결과 및 해시 비교
- 공식 근거 URL 접근성 검사

## 검증 결과

- 검증일: 2026-11-10
- 대상 공종: 3개
- 확장 후보: 51개
- 내부 gold 일치: 51/51
- competency question: 51/51
- 결함 주입 검출: 312/312
- 독립 반복 실행: 10회
- 산출물 해시: 10회 동일
- 공식 출처 접근성: 8/8
- 릴리스 검사: 15/15 통과
- OWL 2 DL 및 HermiT 검사: 통과

## 주요 파일

```text
.
├── README.md
├── environment.yml
├── requirements-validation.txt
├── KO/OWL2/                         # 철근콘크리트 참조 온톨로지
└── final_tbox/
    ├── README.md                    # 상세 실행 설명
    ├── WBS.md                       # 우수공·유도등 WBS
    ├── WBS_EVIDENCE.md              # WBS 근거 추적표
    ├── FINAL_REPORT.md              # 검증 결과
    ├── RELEASE_CHECKLIST.md         # 배포 점검표
    ├── benchmarks/
    │   ├── multitrade_candidates.json
    │   └── multitrade_gold.json
    ├── outputs/multitrade/          # 공종별 OWL·TTL·manifest
    ├── reports/                     # 기계 검증 결과
    ├── tests/                       # 회귀 및 변조 검사
    └── release_multitrade.py        # 전체 실행 파일
```

- [WBS](final_tbox/WBS.md)
- [WBS 근거표](final_tbox/WBS_EVIDENCE.md)
- [최종 검증 보고서](final_tbox/FINAL_REPORT.md)
- [배포 점검표](final_tbox/RELEASE_CHECKLIST.md)
- [전문가 검토 절차](final_tbox/MULTITRADE_EXPERT_REVIEW_PROTOCOL.md)

## WBS 작성 근거

- 타일공사
  - KCS 41 48 01 「타일공사」
- 우수공
  - KCS 11 40 25 「노면배수」
  - KCS 11 40 15 「배수관」
  - KCS 11 20 25 「되메우기 및 뒤채움」
  - KCS 12 20 10 「배수공사 측량」
- 유도등 설비공사
  - NFPC 303 「유도등 및 유도표지의 화재안전성능기준」
  - NFTC 303 「유도등 및 유도표지의 화재안전기술기준」
  - 「소방시설 자체점검사항 등에 관한 고시」

## 결과 사용 시 주의사항

- 검증 수치는 현재 3개 공종 벤치마크에 한정
- 제4공종에 대한 일반화 성능은 별도 평가 필요
- 현장 WBS·물량·일정 자동 생성에는 사용하지 않음
- 법정·설계·감리 검토를 대체하지 않음
- 배포 전 공종별 실무전문가 검토 필요
