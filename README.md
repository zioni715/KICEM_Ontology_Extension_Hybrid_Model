# KICEM Ontology Extension Hybrid Model

## 1. 프로젝트

- 목적: 기존 철근콘크리트 OWL2 기반의 독립 타일공사 온톨로지 구축
- 입력: 기존 온톨로지, 타일공사 WBS, 기성검사원
- 처리 순서: **OmEGa → TaxoPro → MILA → TaxoAdapt → LOREx**
- 주요 기능: 문서 정보 추출, 개념 대응, 분류체계 확장, 후보 검증
- 확장 범위: WBS에 없는 개념도 문서 근거를 바탕으로 후보에 포함
- 구현 방식: OmEGa·LOREx는 논문 기반 구현, 나머지는 복제 소스 활용

## 2. 구축 환경

| 항목 | 설정 |
|---|---|
| 운영체제 | Ubuntu 24.04.3 LTS · x86_64 |
| Conda 환경 | `hybrid-v1` |
| Python | 3.11.15 |
| PyTorch | 2.4.0 · CUDA 런타임 12.1 |
| Transformers | 4.46.3 |
| vLLM | 0.6.3.post1 |
| OpenAI SDK | 1.52.2 |
| RDFLib / Owlready2 | 7.0.0 / 0.48 |
| OWL 추론기 | HermiT · Java 17 |
| API 모델 | `gpt-4o-mini-2024-07-18` |
| 로컬 생성 모델 | `meta-llama/Llama-3.1-8B-Instruct` |
| 인코더 / 임베딩 | `google-bert/bert-base-multilingual-cased` / `intfloat/multilingual-e5-small` |

- 패키지 버전 관리: `requirements.txt`
- 모델 revision·실행 설정: `test2/configs/`, `test2/reports/final_environment.json`

## 3. 컴퓨터 사양

| 항목 | 사양 |
|---|---|
| CPU | AMD Ryzen 5 5600X · 6코어 12스레드 |
| RAM | 16GB |
| GPU | NVIDIA GeForce RTX 3090 · VRAM 24GiB |
| NVIDIA 드라이버 | 550.163.01 |
| Swap | 4GiB |

## 4. 파일 구조

```text
KICEM_Ontology_Extension_Hybrid_Model/
├── README.md
├── requirements.txt
├── .gitignore
├── .env                         # API 키와 Hugging Face 토큰
├── Datasets/                    # 원본 기성검사원
├── KO/OWL2/                     # 기존 철근콘크리트 OWL2
├── KCS_41_48_01_타일공사_시공구조.md  # 타일 WBS
├── Papers/                      # 참고 논문
├── TaxoPro/                     # clone 원본
├── MILA/                        # clone 원본
├── taxoadapt/                   # clone 원본
├── test/                        # 이전 실험, BERT·임베딩 모델, Java
└── test2/
    ├── resume.py                # 완료 확인 및 중단 단계 재개
    ├── configs/                 # 실험·모델 설정
    ├── shared/                  # 공통 코드와 입력 구조
    ├── runtime/                 # 로컬 Llama 모델
    ├── module1/                 # OmEGa 기반 문서 추출
    ├── module2/                 # TaxoPro 학습·후보 순위
    ├── module3/                 # MILA 개념 대응
    ├── module4/                 # TaxoAdapt 분류체계 확장
    ├── module5/                 # LOREx·근거 검사·OWL2 생성·검증
    ├── reports/                 # 통합 보고서와 실행 기록
    └── visualization/           # 온톨로지 탐색 화면
```

- 실행 파일: 각 모듈 폴더
- 산출물: 각 모듈의 `outputs/`
- 보고서: 각 모듈의 `reports/`

## 5. 실행 방법

- 실행 위치: 프로젝트 루트
- 실행 브랜치: `exp/Hybrid-v1`
- 사전 준비: 비공개 입력 자료, 복제 소스, 로컬 모델, Java
- 인증 설정: `.env`에 `OPENAI_API_KEY`, `HF_TOKEN` 지정
- 실행 순서: Module1 → Module2 → Module3 → Module4 → Module5
- GPU 사용 모듈: 앞선 실행 종료 후 순차 실행

**환경 준비**

- 환경 생성·패키지 설치: 최초 구성 시 실행

```bash
conda create -n hybrid-v1 python=3.11 -y
conda activate hybrid-v1
conda install pip
pip install --upgrade
pip install -r requirements.txt --index-url https://pypi.org/simple
python test2/resume.py
```

**Module1 — 문서 추출·초기 온톨로지 구성**

- 입력: 기성검사원, 타일 WBS, `KO/OWL2`
- `prepare.py`: 원본 행·WBS·기존 온톨로지 정보 준비
- `run.py`: API 기반 추출 및 `schema.py`를 통한 초기 구조 생성

```bash
python test2/module1/prepare.py
python test2/module1/run.py
```

**Module2 — TaxoPro 학습·부모 후보 순위**

- 선행 조건: Module1 결과, 복제한 TaxoPro 소스, 로컬 BERT 모델

```bash
python test2/module2/run.py
```

**Module3 — MILA 개념 대응**

- 선행 조건: Module1 결과, 복제한 MILA 소스, 로컬 임베딩 모델
- 처리: 후보 검색 및 API 기반 의미 대응 확인

```bash
python test2/module3/run.py
```

**Module4 — TaxoAdapt 분류체계 확장**

- 선행 조건: Module1–3 결과, 복제한 TaxoAdapt 소스, 로컬 Llama 모델
- 처리: 기존 분류·너비 확장·깊이 확장

```bash
python test2/module4/run.py
```

**Module5 — LOREx 검토·OWL2 생성·검증**

- 선행 조건: 앞선 모듈 결과, 로컬 BERT·Llama 모델, Java
- 실행 순서: 경로 순위 학습 → LOREx 검토 → 검토 기준 점검 → 근거 검사 → 규칙 필터 → OWL2 생성 → 검증

```bash
python test2/module5/rank.py
python test2/module5/run.py
python test2/module5/calibrate_audit.py
python test2/module5/audit.py
python test2/module5/grounding_rules.py
python test2/module5/export.py
python test2/module5/validate.py
```

**통합 보고서·탐색 화면 생성**

- 선행 조건: Module5 검증 완료

```bash
python test2/shared/finalize.py
```

- 개별 실행: 기존 산출물 덮어쓰기 가능
- Module5 근거 검사: 저장된 이전 판정 스냅샷 재사용
- 새 입력·설정 실험: 기존 `test2` 결과와 분리 필요
- 결과 확인 경로:
  - 보고서: `test2/reports/TEST2_REPORT.md`
  - OWL2: `test2/module5/outputs/tile_standalone.owl`
  - 검증: `test2/module5/reports/validation.json`
  - 탐색 화면: `test2/visualization/tile_ontology.html`
