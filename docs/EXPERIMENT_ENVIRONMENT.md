# 실험환경

- 기준일: 2026-11-12

## 장비 및 운영체제

| 항목 | 사양 |
|---|---|
| CPU | AMD Ryzen 5 5600X, 6코어 12스레드 |
| 아키텍처 | x86_64 |
| RAM | 16 GB |
| GPU | NVIDIA GeForce RTX 3090, 24 GiB |
| NVMe SSD | SHGP31-1000GM, 1 TB |
| SATA SSD | Samsung SSD 870 EVO, 2 TB |
| HDD | WDC WD20EZBX, 2 TB |
| 운영체제 | Ubuntu 24.04.3 LTS |
| 커널 | 7.0.0-43-generic |
| NVIDIA 드라이버 | 595.99.02 |
| Conda | 26.5.3 |
| Git | 2.43.0 |

## 기존 OWL 검증 환경 기록

- 과거 검증용 환경. 신규 설치 불필요

| 항목 | 버전·설정 |
|---|---|
| Conda 환경 | `kicem-tbox-validation` |
| Python | 3.11.18 |
| OpenJDK | 17.0.18-internal |
| javac | 17.0.18-internal |
| RDFLib | 7.0.0 |
| Owlready2 | 0.48 |
| NetworkX | 3.3 |
| pip-audit | 2.10.1 |
| OWL 검증 도구 | OWLAPI, HermiT (Owlready2 포함 JAR) |
| 실행 장치 | CPU |

## 하이브리드 실험 환경

- 타일공사·우수공·유도등 설비공사 T-Box 확장 실험 모두 `hybrid-v1`에서 실행.
- 최종 OWL 검증도 해당 파이프라인에서 호출. Java 17은 `kicem-tbox-validation`의 실행 파일 사용.
- 회귀검사: 기존 검증 환경 및 `hybrid-v1`에서 각각 20건 통과

| 항목 | 버전·설정 |
|---|---|
| Conda 환경 | `hybrid-v1` |
| Python | 3.11.15 |
| PyTorch | 2.4.0+cu121 |
| CUDA 런타임 (PyTorch) | 12.1 |
| Transformers | 4.46.3 |
| vLLM | 0.6.3.post1 |
| Sentence Transformers | 3.0.1 |
| PEFT | 0.13.2 |
| NumPy | 1.26.4 |
| OpenAI SDK | 1.52.2 |
| HTTPX | 0.27.2 |
| 실행 장치 | NVIDIA GeForce RTX 3090 |
| 최종 OWL 검사 Java | 환경변수 → PATH → 같은 Conda envs 경로의 `kicem-tbox-validation/bin/` 순서 탐색 |

- GPU 실행: TaxoPro·TEMPORA 학습, Llama 추론·계보 점수 계산.
- CPU 실행: E5 임베딩·검색, OWLAPI·HermiT 검사.
- 원격 API: `gpt-4o-mini-2024-07-18`. 모델 추론은 OpenAI 서버에서 수행.
- `requirements.txt`: 위 실험 버전 기준 3공종 GPU·API·데이터 처리·OWL 패키지 통합.
- `environment.yml`: 신규 `hybrid-v1`용 Python 3.11·Java 17 및 requirements 설치 정의.
- 신규 설치: `hybrid-v1` 하나로 통합. 새 환경 전체 설치 검증 미실시

## 신규 통합 환경 설치

- 환경 설정: [environment.yml](../environment.yml)
- Python 의존성: [requirements.txt](../requirements.txt)
- 실행 위치: 저장소 루트

```bash
conda env create -f environment.yml
conda activate hybrid-v1
python -m pip check
```

- 기존 환경 갱신:

```bash
conda activate hybrid-v1
python -m pip install -r requirements.txt
python -m pip check
```
