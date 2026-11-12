# 비용산정 기성서류 온톨로지 T-Box 자동확장 모델

- 목적: 철근콘크리트 공종에서 정리한 공통 작업유형을 활용한 공종별 T-Box 확장
- 대상: 타일공사, 우수공, 유도등 설비공사

## 1. 모델 개요

- 처리 순서: 근거·WBS → 추출 → TaxoPro → MILA → TaxoAdapt → TEMPORA·LOREx → T-Box 출력·검증

- 공통 코드: `hybrid_multitrade/pipeline/` 한 벌. 공종별 Python 코드 생성·복제 없음
- 공종 설정: `hybrid_multitrade/pipeline/configs/trades.json`. 입력과 실행 데이터만 공종별 분리
- 전체 실행: `python hybrid_multitrade/run.py` 한 번으로 세 공종 순차 처리
- 입력: 공개 기준에서 정규화한 작업 설명(식별자·라벨·정의·출처·조항)
- 출력: 클래스, 상속 관계, 주석 및 근거 정보를 포함한 독립 T-Box
- 현장·층·공구·물량·단가·일정 등 A-Box 정보는 제외

| 공종 | 입력 근거 | 기준 기반 입력 건수 |
|---|---|---:|
| 타일공사 | KCS 41 48 01 | 24 |
| 우수공 | KCS 11 40 25·11 40 15·11 20 25·12 20 10 | 12 |
| 유도등 설비공사 | NFPC 303, NFTC 303, 소방시설 자체점검 고시 | 15 |
| 합계 | 공식 출처 8건 | 51 |


### 사용 모델

| 적용 범위 | 용도 | 모델 |
|---|---|---|
| 3공종 하이브리드 재실험 | OpenAI API 기반 추출·판정 | `gpt-4o-mini-2024-07-18` |
| 3공종 하이브리드 재실험 | 로컬 LLM | `meta-llama/Llama-3.1-8B-Instruct` |
| 3공종 하이브리드 재실험 | 임베딩·후보 검색 | `intfloat/multilingual-e5-small` |
| 3공종 하이브리드 재실험 | TaxoPro·TEMPORA 인코더 | `google-bert/bert-base-multilingual-cased` |


## 2. 저장소 구성

<details>
<summary>Git 업로드 대상 전체 파일·폴더 보기</summary>

```text
.  # 저장소 루트
├── .github/                                                      # GitHub 자동화 설정
│   └── workflows/                                                # push·PR 시 실행할 작업 정의
│       └── tbox-validation.yml                                   # 의존성·단위검사·반복 검증 CI
├── docs/                                                         # 모델·실험환경 설명서
│   ├── EXPERIMENT_ENVIRONMENT.md                                 # 장비 사양·환경별 패키지 버전
│   └── MODEL_GUIDE.md                                            # 하이브리드 구성·입력·검증·실행 상태
├── hybrid_multitrade/                                            # 기존 하이브리드 모델의 공종별 재실험
│   ├── inputs/                                                   # 공종별 기준 기반 입력
│   │   └── trade_candidates.json                                 # 3공종 작업 설명·출처·조항(부모 정답 없음)
│   ├── pipeline/                                                 # 모든 공종이 함께 쓰는 단일 모델 구현
│   │   ├── configs/                                              # 공통 모델·공종 설정
│   │   │   ├── llama_model.json                                  # Llama 모델·revision 고정
│   │   │   ├── llama_runtime.json                                # 계층 확장용 추론 설정
│   │   │   ├── llama_scoring_runtime.json                        # 계보 점수용 추론 설정
│   │   │   └── trades.json                                       # 공종명·식별자·클래스 접두어
│   │   ├── shared/                                               # 모든 단계의 공통 처리
│   │   │   ├── common.py                                         # API·캐시·입출력·모델 경로
│   │   │   ├── domain.py                                         # 실행 시 공종 설정 적용
│   │   │   └── seed_elements.json                                # 재사용할 기준 온톨로지 요소
│   │   ├── module1/                                              # 근거 추출·초기 스키마
│   │   │   ├── run.py                                            # 구조화 추출
│   │   │   └── schema.py                                         # 초기 클래스·속성·가설 생성
│   │   ├── module2/                                              # TaxoPro
│   │   │   └── run.py                                            # 부모 후보 학습·순위
│   │   ├── module3/                                              # MILA
│   │   │   └── run.py                                            # 양방향 개념 정합
│   │   ├── module4/                                              # TaxoAdapt
│   │   │   ├── adapters/                                         # 로컬 LLM 실행 어댑터
│   │   │   │   └── local_runtime.py                              # 단일 GPU Llama 초기화
│   │   │   └── run.py                                            # 근거 분류·폭·깊이 확장
│   │   └── module5/                                              # TEMPORA·LOREx·근거 감사
│   │       ├── rank.py                                           # 계보 순위 학습
│   │       ├── run.py                                            # 부모 검색·계보·의미 검토
│   │       ├── audit.py                                          # 최종 원문 근거 감사
│   │       └── grounding_rules.py                                # 기존 파일럿의 보수적 근거 필터
│   ├── results/                                                  # 실제 실행 상태·완료 결과
│   │   ├── architecture_tile.json                                # 타일 후보별 결과·근거·검증·해시
│   │   ├── architecture_tile.owl                                 # 타일 최종 T-Box RDF/XML
│   │   ├── architecture_tile.ttl                                 # 타일 최종 T-Box Turtle
│   │   ├── civil_stormwater.json                                 # 우수공 후보별 결과·근거·검증·해시
│   │   ├── civil_stormwater.owl                                  # 우수공 최종 T-Box RDF/XML
│   │   ├── civil_stormwater.ttl                                  # 우수공 최종 T-Box Turtle
│   │   ├── fire_exit_guidance.json                               # 유도등 후보별 결과·근거·검증·해시
│   │   ├── fire_exit_guidance.owl                                # 유도등 최종 T-Box RDF/XML
│   │   ├── fire_exit_guidance.ttl                                # 유도등 최종 T-Box Turtle
│   │   ├── STATUS.json                                           # 공종별 실행·완료 상태
│   │   ├── summary.json                                          # 3공종 실행 결과 집계
│   │   ├── token_usage.json                                      # 공종별 실제 API 입력·출력 토큰 집계
│   │   └── verification.json                                     # 실제 회귀검사 실행 결과
│   ├── tests/                                                    # 입력·학습조건 보존 검사
│   │   ├── test_protocol.py                                      # gold 분리·고정 설정 검사
│   │   ├── test_results.py                                       # 산출물·집계·근거·해시 대조
│   │   ├── test_status.py                                        # 실행 상태·완료 판정 검사
│   │   ├── test_tbox_export.py                                   # 명시·암시적 A-Box 주입 차단 검사
│   │   ├── test_unified_pipeline.py                              # 단일 코드·공종 설정·통합 전후 동등성 검사
│   │   └── test_validation.py                                    # 입력 정합성·실제 추론기 대조검사
│   ├── validators/                                               # 공통 온톨로지 검증기
│   │   └── java/                                                 # Java 기반 OWL 검증기
│   │       ├── ValidateHermit.java                               # 일관성·명명 클래스 만족 가능성 검사
│   │       └── ValidateOntology.java                             # OWL 2 DL·직렬화 동등성 검사
│   ├── owl_validation.py                                         # 독립 OWLAPI·HermiT 실행 도구
│   ├── README.md                                                 # 고정 조건·입력 변경·실행 상태
│   ├── RESULTS.md                                                # 공종별 결과·후보 목록·검증 한계
│   ├── report.py                                                 # 기록에서 결과 설명서 생성
│   ├── run.py                                                    # 단일 공통 파이프라인 실행 진입점
│   ├── tbox_export.py                                            # T-Box 전용 생성·A-Box assertion 차단
│   └── verify.py                                                 # 회귀검사 실행·결과 JSON 기록
├── KO/                                                           # 기준 온톨로지 자료
│   └── OWL2/                                                     # 철근콘크리트 OWL 2 참조 모델
│       ├── axioms.md                                             # 기준 온톨로지의 공리 명세
│       ├── OWL2_VALIDATION_REPORT.md                             # 철근콘크리트 OWL 2 검증 보고서
│       ├── owl2-shapes.ttl                                       # SHACL 구조·데이터 검증 제약
│       ├── rcpp-owl-final.ttl                                    # 철근콘크리트 기준 온톨로지
│       ├── rcpp-owl-inferred.ttl                                 # 기준 온톨로지의 추론 결과
│       └── validate_owl2.py                                      # 기준 OWL 2·SHACL 검증 실행
├── wbs/                                                          # 3공종 WBS 및 근거
│   ├── EVIDENCE.md                                               # 공식 기준·조항별 근거 추적표
│   ├── exit_guidance.md                                          # 소방 유도등 설비공사 WBS
│   ├── README.md                                                 # 공종별 WBS 목록·작성 범위
│   ├── stormwater.md                                             # 토목 우수공 WBS
│   └── tile.md                                                   # 건축 타일공사 WBS
├── .gitignore                                                    # 비공개 자료·인증정보·캐시 제외
├── environment.yml                                               # Conda의 Python·Java 환경 정의
├── README.md                                                     # 프로젝트 소개·설치·실행 안내
└── requirements.txt                                              # 배포용 Python 패키지·고정 버전
```

</details>

## 3. 실험환경 및 인증 설정

### 3.1 사용한 Conda 환경

- 사용 환경: `hybrid-v1` 하나로 3공종 확장·결과 생성·검증 수행

| 환경명 | 사용하는 경우 | Python | 주요 연산 |
|---|---|---|---|
| `hybrid-v1` | 타일·우수공·유도등 확장, OWL·TTL 생성, 최종 검증·회귀검사 | 3.11.15 | GPU 학습·추론 + CPU 처리 |

- GPU: RTX 3090 24 GiB, PyTorch 2.4.0+cu121, CUDA 런타임 12.1. TaxoPro·TEMPORA 학습과 Llama 추론에 사용.
- 같은 파이프라인의 E5 검색·OWL 검사는 CPU에서 처리하고, GPT-4o-mini 호출은 원격 API로 처리했다.
- `hybrid-v1`에서 회귀검사 20건 통과 확인.
- `environment.yml`에서 Java 17까지 설치. 별도 검증 환경 생성 불필요.
- 패키지 버전과 장비 사양: [실험환경](docs/EXPERIMENT_ENVIRONMENT.md)

- 3공종 확장·검증 통합 환경 생성(Linux x86_64·NVIDIA GPU):

```bash
conda env create -f environment.yml
conda activate hybrid-v1
python -m pip check
```

- 기존 `hybrid-v1`에 전체 Python 의존성 설치:

```bash
conda activate hybrid-v1
python -m pip install -r requirements.txt
python -m pip check
```

- `requirements.txt`: 3공종 공통 파이프라인의 GPU 학습·추론, API, 데이터 처리, OWL 검증 패키지 통합.
- `environment.yml`: `hybrid-v1` 생성 → Python 3.11·Java 17 설치 → 위 requirements 적용.
- 모델 가중치·수정된 외부 소스는 별도 준비. 전체 신규 환경 설치 검증은 아직 미실시.

- 전체 파이프라인 실행에 필요한 로컬 파일:

| 위치(프로젝트 루트 기준) | 필요한 내용 |
|---|---|
| `tile_case_study/module2/source/TaxoPro/` | 실험에서 사용한 TaxoPro 소스·custom PEFT·설정 파일 |
| `tile_case_study/module3/source/` | 실험에서 사용한 MILA 소스 |
| `tile_case_study/module4/source/` | 실험에서 사용한 TaxoAdapt 소스·호환성 수정본 |
| `hybrid_pipeline/runtime/models.lock.json` | `bert`·`embedding` 항목의 `path`에 실제 로컬 모델 경로 지정 |
| `tile_case_study/runtime/models/llama-3.1-8b-instruct/` | Llama 가중치·토크나이저·설정 파일 |

- 외부 라이브러리: 실험 사용 버전 복원(최신 버전 재현성 미확인)
- BERT·E5: 로컬 모델 경로를 `models.lock.json`에 설정
- Llama: `hybrid_multitrade/pipeline/configs/llama_model.json`의 모델·revision·경로 적용
- 모델 사전 다운로드 필수(실행 중 다운로드 비활성화)
- GPU 의존성·외부 파일 미준비 시: 결과 열람·OWL 검증만 가능

### 3.2 API 키·토큰 설정

#### 1) 키·토큰 발급

| 서비스 | 발급 순서 | 용도 |
|---|---|---|
| Hugging Face | 로그인 → [Settings / Access Tokens](https://huggingface.co/settings/tokens) → **New token** → 이름 입력 → **Read** 권한 → 생성·복사 | 로컬 모델 다운로드 |
| OpenAI | 로그인 → 프로젝트 선택 → [API keys](https://platform.openai.com/api-keys) → **Create new secret key** → 생성·복사 | `gpt-4o-mini-2024-07-18` API 호출 |

- Hugging Face 접근 제한 모델은 모델 페이지에서 약관 동의·접근 승인 필요.
- OpenAI 프로젝트는 해당 모델 사용 권한과 사용 가능한 한도 필요.

#### 2) `.env`에 저장

- 프로젝트 루트의 `.env`에 아래 두 항목을 작성하고 우변을 본인의 실제 값으로 교체.
```dotenv
HF_TOKEN=본인의_Hugging_Face_토큰
OPENAI_API_KEY=본인의_OpenAI_API_키
```

#### 3) 코드에서 불러오기

- 공통 하이브리드 파이프라인은 프로젝트 루트의 `.env`를 읽음.
```python
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env", override=False)
hf_token = os.environ["HF_TOKEN"]
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
```

- `HF_TOKEN`: 모델 다운로드 시 인증 토큰으로 전달.
- `OPENAI_API_KEY`: OpenAI 클라이언트 인증에 사용.
- 이미 설정된 환경변수가 있으면 `.env` 값보다 우선.
- `.env`는 Git 제외 대상. 실제 키·토큰은 공유하지 않음.
- 공식 안내: [Hugging Face](https://huggingface.co/docs/hub/security-tokens), [OpenAI](https://developers.openai.com/api/docs/quickstart)

## 4. 실행 및 결과 확인

- 하이브리드 재실험(유효한 OpenAI 키 필요):

```bash
conda activate hybrid-v1
python hybrid_multitrade/run.py
```

- 완료된 단계는 재사용하고 최종 T-Box를 재검증. 입력·모델 설정 변경 시 기존 실행 재사용 차단.
- Java 17 필요. `environment.yml`로 설치.
- 고정 조건·입력 차이·실행 상태: [재실험 안내](hybrid_multitrade/README.md)

- 산출물·회귀검사:

```bash
conda activate hybrid-v1
python hybrid_multitrade/verify.py
```

- 실험 장비 회귀검사: 20건 통과
- 새 clone: 로컬 자료 의존 검사 일부 생략 가능. `hybrid_multitrade/results/verification.json`의 `skipped` 확인

## 5. 실험 상태

| 공종 | 후보 | 채택 | 보류 | 최종 클래스 | 논리·구조 검사 |
|---|---:|---:|---:|---:|---|
| 타일공사 | 18 | 10 | 8 | 39 | 통과 |
| 우수공 | 17 | 6 | 11 | 35 | 통과 |
| 유도등 설비공사 | 19 | 8 | 11 | 37 | 통과 |

- 최종 클래스 = 재사용 23개 + 연구자 정의 앵커 6개 + 공종별 채택 후보.
- 순수 T-Box, 계층 비순환, OWL·TTL 동등성, OWL 2 DL, HermiT 검사 통과. 개체 0개.
- 채택 수는 정확도가 아님. 독립 의미 정확도·재현율·F1은 미측정.
- 입력은 공개 기준 설명이며 기존 비공개 기성서류 실험과 동일 입력 조건은 아님.
- 상세 결과: [공종별 결과·후보 목록](hybrid_multitrade/RESULTS.md)
- 실행 기록: [STATUS.json](hybrid_multitrade/results/STATUS.json)
- 원본 RC OWL 전체 공리를 무손실로 통합한 결과는 아님. 공통 클래스 계층을 재사용한 공종별 T-Box.

## 6. 참고 문서

| 문서 | 내용 |
|---|---|
| [모델 설명서](docs/MODEL_GUIDE.md) | 자동확장 방식·검증 방법·결과 해석 |
| [실험환경](docs/EXPERIMENT_ENVIRONMENT.md) | 장비 사양·환경별 버전 |
| [공종별 WBS](wbs/README.md) | 타일·우수·유도등 작업분류 |
| [WBS 근거표](wbs/EVIDENCE.md) | 공식 기준·조항 추적 |
