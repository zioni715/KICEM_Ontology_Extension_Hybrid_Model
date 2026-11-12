"""Summarize recorded experiments, without manufacturing evaluation scores."""
from pathlib import Path
from decimal import Decimal
import json

HERE = Path(__file__).resolve().parent
LABELS = {"architecture_tile": "타일공사", "civil_stormwater": "우수공",
          "fire_exit_guidance": "유도등 설비공사"}


def estimate_cost(item):
    cached = item.get("provider_cached_prompt_tokens", 0)
    input_cost = (Decimal(item["prompt_tokens"] - cached) * Decimal("0.15") +
                  Decimal(cached) * Decimal("0.075")) / Decimal(1000000)
    output_cost = Decimal(item["completion_tokens"]) * Decimal("0.60") / Decimal(1000000)
    return input_cost, output_cost, input_cost + output_cost


def token_usage():
    """Aggregate provider usage once per response, across original/unified runs."""
    destination = HERE / "results/token_usage.json"
    logs = [HERE / ".runs" / trade / "reports/api_calls.jsonl" for trade in LABELS]
    if not all(path.exists() for path in logs):
        return json.loads(destination.read_text()) if destination.exists() else None
    trades = {}
    for trade, original in zip(LABELS, logs):
        seen = set()
        counts = dict(prompt_tokens=0, completion_tokens=0, total_tokens=0,
                      provider_cached_prompt_tokens=0, successful_api_calls=0)
        for path in [original, HERE / ".runs/unified" / trade / "reports/api_calls.jsonl"]:
            if not path.exists():
                continue
            for line in path.read_text().splitlines():
                call = json.loads(line)
                if not call.get("usage") or call.get("cache_hit"):
                    continue
                key = call.get("response_id") or (str(path), call.get("request_hash"), call.get("attempt"))
                if key in seen:
                    continue
                seen.add(key)
                usage = call["usage"]
                for field in ["prompt_tokens", "completion_tokens", "total_tokens"]:
                    counts[field] += usage.get(field, 0)
                counts["provider_cached_prompt_tokens"] += usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                counts["successful_api_calls"] += 1
        trades[trade] = counts
    result = {"model": "gpt-4o-mini-2024-07-18",
              "scope": "Provider-reported OpenAI usage across original and unified runs, deduplicated by response_id; local Llama/BERT/E5 tokens excluded",
              "trades": trades,
              "total": {field: sum(item[field] for item in trades.values()) for field in counts}}
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def render():
    lines = ["# 하이브리드 T-Box 재실험 결과", "",
             "- 입력: 공개 기준에서 정규화한 작업 설명. 비공개 기성서류 미사용.",
             "- 모델: 기존 타일 파일럿의 GPT-4o-mini·BERT·E5·Llama 3.1 8B 구성 및 학습 설정 유지.",
             "- 출력: T-Box만 포함. A-Box 생성기 미실행.",
             "- 승인율은 정확도가 아님. 독립 전문가 정답이 없어 의미 정확도·재현율·F1은 산출하지 않음.", "",
             "- 통합 실행은 동일 요청의 기존 응답 캐시를 재사용하며 캐시 적중과 신규 API 호출을 구분. 독립 반복실험으로 해석하지 않음.", "",
             "## 공종별 산출물", "",
             "| 공종 | 상태 | 입력 | 후보 | 최종 포함 후보 | 보류 | 전체 클래스 | 데이터 속성 | 논리·구조 검사 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    results = []
    for trade, label in LABELS.items():
        path = HERE / "results" / (trade + ".json")
        result = json.loads(path.read_text()) if path.exists() else {"status": "NOT_EXECUTED"}
        results.append((trade, label, result))
        values = [str(result.get(key, "—")) for key in
                  ["input_rows", "proposal_count", "exported_accepted", "held", "classes", "data_properties"]]
        checks = result.get("checks", {}).get("passed")
        lines.append(f'| {label} | {result["status"]} | ' + " | ".join(values) +
                     " | " + ("통과" if checks is True else "미완료") + " |")
    usage = token_usage()
    if usage:
        lines += ["", "## 3공종 API 토큰 사용량", "",
                  "- 모델: `gpt-4o-mini-2024-07-18`. API 응답의 `usage` 실측 합계.",
                  "- 최초 실행과 통합 실행의 실제 API 응답을 합산하고 응답 ID로 중복 제거.",
                  "- 로컬 응답 캐시 재사용은 신규 API 토큰 0개. 실패 응답에 usage가 없으면 합산하지 않음.",
                  "- 로컬 Llama 추론 및 BERT·E5 학습·임베딩 토큰은 아래 API 집계에 포함하지 않음.", "",
                  "| 공종 | API 성공 호출 | 입력 토큰 | 출력 토큰 | 총 토큰 |",
                  "|---|---:|---:|---:|---:|"]
        for trade, label in [*LABELS.items(), ("total", "합계")]:
            item = usage["total"] if trade == "total" else usage["trades"][trade]
            lines.append(f'| {label} | {item["successful_api_calls"]:,} | {item["prompt_tokens"]:,} | {item["completion_tokens"]:,} | {item["total_tokens"]:,} |')
        lines += ["", "- 집계 기록: [token_usage.json](results/token_usage.json). 입력 토큰에는 API 제공자가 집계한 캐시 입력도 포함."]
        lines += ["", "### 토큰 기준 예상 API 비용", "",
                  "- 적용 단가: 100만 토큰당 입력 $0.15, API 캐시 입력 $0.075, 출력 $0.60. 일반 동기 호출 기준(Batch 할인 미적용).",
                  "- 단가 확인일: 2026-11-12. 출처: [OpenAI 공식 GPT-4o Mini 가격](https://developers.openai.com/api/docs/models/gpt-4o-mini).",
                  "- 계산식: (입력−API 캐시 입력)×0.15/1,000,000 + API 캐시 입력×0.075/1,000,000 + 출력×0.60/1,000,000.",
                  "- 이번 API 캐시 입력은 0토큰. 로컬 응답 캐시 재사용에는 추가 API 비용이 없음.", "",
                  "| 공종 | 입력 비용(USD) | 출력 비용(USD) | 합계(USD) |",
                  "|---|---:|---:|---:|"]
        for trade, label in [*LABELS.items(), ("total", "합계")]:
            item = usage["total"] if trade == "total" else usage["trades"][trade]
            amounts = estimate_cost(item)
            lines.append(f'| {label} | ' + " | ".join(f"${amount:.8f}" for amount in amounts) + " |")
        lines += ["", "- 사용 로그와 공식 단가로 산출한 예상액이며 실제 청구서 확인액은 아님. 세금·환율·카드 수수료·계정 할인 및 로컬 GPU 전력·장비 비용 제외."]
    lines += ["", "## 검증 범위", "",
              "- 순수 T-Box: 명명·암시적 개체, 일반 속성값 assertion 차단.",
              "- 계층: 순환 및 보류된 부모에 매달린 후보 제외.",
              "- 직렬화: OWL·TTL 그래프 동등성 확인.",
              "- OWLAPI: OWL 2 DL 프로파일 확인.",
              "- HermiT: 온톨로지 일관성 및 명명 클래스 불만족 여부 확인.",
              "- 근거 감사: API 의미 검토와 원문 인용 대조. 독립 전문가 검증은 아님.",
              "- 한계: 원본 타일 파일럿의 보수적 근거 필터도 유지하므로 타 공종에서 과도한 보류 가능.",
              "- 한계: 독립 공종별 T-Box 출력이며 원본 RC OWL 전체 공리의 무손실 통합을 검증한 것은 아님.", ""]
    verification = HERE / "results/verification.json"
    if verification.exists():
        check = json.loads(verification.read_text())
        lines += [f'- 회귀검사: {check["tests_run"]}건 실행, 실패 {check["failures"]}건, 오류 {check["errors"]}건, 생략 {check["skipped"]}건. [실행 기록](results/verification.json).', ""]
    for trade, label, result in results:
        lines += [f"## {label}", "", f"- 상세 기록: [JSON](results/{trade}.json)."]
        if result.get("status") != "COMPLETED_TBOX":
            lines += ["- 최종 검증 완료 결과 없음.", ""]
            continue
        lines += [f'- 검증 통과 산출물: [OWL](results/{trade}.owl), [TTL](results/{trade}.ttl).',
                  f'- 통합 실행의 신규 API 호출: 성공 {result.get("api_successful_calls", "미집계")}회, 실패 {result.get("api_failed_calls", "미집계")}회. 최초 생성 호출은 위 토큰·비용 표에 포함.',
                  f'- 동일 요청 캐시 재사용: {result.get("api_cache_hits", 0)}회.',
                  f'- 클래스 구성: 재사용 {result.get("retained_seed_classes", "—")}개 + 연구자 정의 앵커 {result.get("researcher_anchor_classes", "—")}개 + 채택 후보 {result["exported_accepted"]}개.',
                  f'- TaxoAdapt 신규 제안: {result.get("module4", {}).get("generated_candidates", "미집계")}개.',
                  f'- 최종 후보가 인용한 입력 설명: {result.get("evidence_input_coverage_count", "미집계")}/{result["input_rows"]}건. 의미 재현율이 아닌 근거 인용 범위.',
                  f'- TaxoPro RC seed 부모 복원: {result.get("module2", {}).get("heldout_top1", "—")}/{result.get("module2", {}).get("heldout_count", "—")}. 공종 확장 정확도가 아닌 소규모 내부 진단.',
                  "- 후보별 결과:", "",
                  "| 후보 | 상태 | 선택 부모 | 최종 포함 |", "|---|---|---|---|"]
        for item in result.get("candidate_outcomes", []):
            label_text = item["label"].replace("|", "/").replace("\n", " ")
            lines.append(f'| {label_text} | {item["status"]} | {item.get("selected_parent") or "—"} | {"예" if item["exported"] else "아니오"} |')
        lines.append("")
    (HERE / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    render()
