# RCPP OWL 2 Axiom Specification

- Ontology IRI: `https://zioni715.github.io/ontology/rcpp`
- Namespace: `https://zioni715.github.io/ontology/rcpp#`
- 대상 언어: OWL 2
- 구현 도구: Protégé Desktop
- 논리 검증: HermiT Reasoner
- 공리 설계 기준: 기존 RDFS 구조, 도메인 의미, 문서 간 정보전달 관계, 데이터 제약
- 비고: 산술식 및 실제 데이터 유효성 검사는 OWL 공리와 분리하여 SHACL에서 수행

---

# Ⅰ. 클래스 분류 및 상호배타성

## A01. 기성서류의 분류

현재 온톨로지 범위의 기성서류는 근거서류 또는 산출서류 중 정확히 하나에 속하며, 하나의 기성서류가 동시에 근거서류와 산출서류에 속할 수 없다.

`disjointUnionOf`

```text
ProgressDocument
disjointUnionOf
    EvidenceDocument
    OutputDocument
```

---

## A02. 근거서류의 분류

현재 온톨로지 범위의 근거서류는 수량산출서, 계약내역서, 원가계산서, 공종별내역서 또는 공종별집계표 중 정확히 하나의 유형에 속하며, 동시에 둘 이상의 유형에 속할 수 없다.

`disjointUnionOf`

```text
EvidenceDocument
disjointUnionOf
    QuantityCalculationSheet
    ContractStatement
    CostCalculationStatement
    WorkCategoryDetailStatement
    WorkCategorySummaryStatement
```

---

## A03. 비용항목의 공종별 분류

현재 온톨로지 범위의 비용항목은 철근 비용항목, 콘크리트 비용항목, 거푸집 비용항목 또는 동바리 비용항목 중 정확히 하나에 속하며, 동시에 둘 이상의 공종 비용항목에 속할 수 없다.

`disjointUnionOf`

```text
CostItem
disjointUnionOf
    RebarCostItem
    ConcreteCostItem
    FormworkCostItem
    ShoringCostItem
```

---

## A04. 철근 비용항목의 세부 분류

철근 비용항목은 철근 재료비항목 또는 철근 가공·조립비항목 중 정확히 하나에 속하며, 동시에 두 유형에 속할 수 없다.

`disjointUnionOf`

```text
RebarCostItem
disjointUnionOf
    RebarMaterialCostItem
    RebarFabricationAssemblyCostItem
```

---

## A05. 콘크리트 비용항목의 세부 분류

콘크리트 비용항목은 레디믹스트콘크리트 재료비항목 또는 콘크리트 타설비항목 중 정확히 하나에 속하며, 동시에 두 유형에 속할 수 없다.

`disjointUnionOf`

```text
ConcreteCostItem
disjointUnionOf
    ReadyMixedConcreteMaterialCostItem
    ConcretePlacementCostItem
```

---

# Ⅱ. 문서별 포함 항목의 유형 제한

## A06. 수량산출서의 포함 항목

수량산출서가 포함하는 모든 항목은 수량산출항목이어야 한다.

**Manchester Syntax**

```text
QuantityCalculationSheet
SubClassOf
    containsItem only CalculatedQuantityItem
```

---

## A07. 계약내역서의 포함 항목

계약내역서가 포함하는 모든 항목은 계약항목이어야 한다.

**Manchester Syntax**

```text
ContractStatement
SubClassOf
    containsItem only ContractItem
```

---

## A08. 원가계산서의 포함 항목

원가계산서가 포함하는 모든 항목은 원가계산항목이어야 한다.

**Manchester Syntax**

```text
CostCalculationStatement
SubClassOf
    containsItem only CostCalculationItem
```

---

## A09. 공종별내역서의 포함 항목

공종별내역서가 포함하는 모든 항목은 공종별내역항목이어야 한다.

**Manchester Syntax**

```text
WorkCategoryDetailStatement
SubClassOf
    containsItem only WorkCategoryDetailItem
```

---

## A10. 공종별집계표의 포함 항목

공종별집계표가 포함하는 모든 항목은 계약집계항목이어야 한다.

**Manchester Syntax**

```text
WorkCategorySummaryStatement
SubClassOf
    containsItem only ContractSummaryItem
```

---

## A11. 공사기성부분내역서의 포함 항목

공사기성부분내역서가 포함하는 모든 항목은 기성내역항목 또는 기성집계항목이어야 한다.

**Manchester Syntax**

```text
ProgressPaymentStatement
SubClassOf
    containsItem only
        (ProgressPaymentItem or ProgressPaymentSummaryItem)
```

---

# Ⅲ. 핵심 객체관계의 개수 제약

## A12. 공사기성부분내역서와 기성회차

하나의 공사기성부분내역서는 정확히 하나의 기성회차에 속한다.

**Manchester Syntax**

```text
ProgressPaymentStatement
SubClassOf
    belongsToProgressRound exactly 1 ProgressPaymentRound
```

---

## A13. 기성서류항목의 소속 문서

하나의 기성서류항목은 정확히 하나의 기성서류에 포함된다.

**Manchester Syntax**

```text
DocumentItem
SubClassOf
    inverse containsItem exactly 1 ProgressDocument
```

---

## A14. 상세비용항목과 비용항목

하나의 상세비용항목은 정확히 하나의 비용항목을 표현한다.

**Manchester Syntax**

```text
DetailItem
SubClassOf
    representsCostItem exactly 1 CostItem
```

---

## A15. 상세비용항목과 단위

하나의 상세비용항목은 정확히 하나의 단위를 사용한다.

**Manchester Syntax**

```text
DetailItem
SubClassOf
    usesUnit exactly 1 Unit
```

---

## A16. 비용항목과 공종

하나의 비용항목은 정확히 하나의 철근콘크리트 세부 공종에 속한다.

**Manchester Syntax**

```text
CostItem
SubClassOf
    belongsToWorkCategory exactly 1 WorkCategory
```

---

## A17. 집계항목과 공종

하나의 집계항목은 정확히 하나의 철근콘크리트 세부 공종에 속한다.

**Manchester Syntax**

```text
SummaryItem
SubClassOf
    belongsToWorkCategory exactly 1 WorkCategory
```

---

# Ⅳ. 문서 간 정보전달 및 원천 관계

## A18. 계약항목의 산출수량 원천

하나의 계약항목에는 산출수량의 원천이 되는 하나 이상의 수량산출항목이 연결된다.

**Manchester Syntax**

```text
ContractItem
SubClassOf
    inverse providesCalculatedQuantityTo some CalculatedQuantityItem
```

---

## A19. 공종별내역항목의 계약값 원천

하나의 공종별내역항목이 사용하는 계약값은 정확히 하나의 계약항목을 원천으로 한다.

**Manchester Syntax**

```text
WorkCategoryDetailItem
SubClassOf
    inverse providesContractValueTo exactly 1 ContractItem
```

---

## A20. 계약집계항목의 집계 원천

하나의 계약집계항목에는 하나 이상의 공종별내역항목이 계약금액 집계의 원천으로 연결된다.

**Manchester Syntax**

```text
ContractSummaryItem
SubClassOf
    inverse contributesContractAmountTo some WorkCategoryDetailItem
```

---

## A21. 기성내역항목의 계약수량 원천

하나의 기성내역항목의 계약수량은 정확히 하나의 계약항목에서 전달된다.

**Manchester Syntax**

```text
ProgressPaymentItem
SubClassOf
    inverse providesContractQuantityToProgressPaymentItem exactly 1 ContractItem
```

---

## A22. 기성내역항목의 계약단가 원천

하나의 기성내역항목의 계약단가는 정확히 하나의 계약항목에서 전달된다.

**Manchester Syntax**

```text
ProgressPaymentItem
SubClassOf
    inverse providesContractUnitPriceToProgressPaymentItem exactly 1 ContractItem
```

---

## A23. 기성내역항목의 계약금액 원천

하나의 기성내역항목의 계약금액은 정확히 하나의 계약항목에서 전달된다.

**Manchester Syntax**

```text
ProgressPaymentItem
SubClassOf
    inverse providesContractAmountToProgressPaymentItem exactly 1 ContractItem
```

---

## A24. 기성내역항목의 전회누계 원천

하나의 기성내역항목은 전회누계값을 제공하는 이전 기성내역항목을 최대 하나만 가질 수 있다.

**Manchester Syntax**

```text
ProgressPaymentItem
SubClassOf
    inverse providesCumulativeValuesTo max 1 ProgressPaymentItem
```

---

# Ⅴ. 데이터값의 개수 제약

## A25. 수량산출항목의 산출수량

하나의 수량산출항목은 정확히 하나의 산출수량 값을 갖는다.

**Manchester Syntax**

```text
CalculatedQuantityItem
SubClassOf
    calculatedQuantity exactly 1 xsd:decimal
```

---

## A26. 계약항목의 계약정보

하나의 계약항목은 계약수량, 계약단가 및 계약금액을 각각 정확히 하나씩 갖는다.

**Manchester Syntax**

```text
ContractItem
SubClassOf
    contractQuantity exactly 1 xsd:decimal,
    contractUnitPrice exactly 1 xsd:decimal,
    contractAmount exactly 1 xsd:decimal
```

---

## A27. 원가계산항목의 단위비용 정보

하나의 원가계산항목은 단위당 재료비, 단위당 노무비, 단위당 경비 및 산출단가를 각각 정확히 하나씩 갖는다.

**Manchester Syntax**

```text
CostCalculationItem
SubClassOf
    materialUnitCost exactly 1 xsd:decimal,
    laborUnitCost exactly 1 xsd:decimal,
    expenseUnitCost exactly 1 xsd:decimal,
    calculatedUnitPrice exactly 1 xsd:decimal
```

---

## A28. 공종별내역항목의 계약정보

하나의 공종별내역항목은 계약수량, 계약단가 및 계약금액을 각각 정확히 하나씩 갖는다.

**Manchester Syntax**

```text
WorkCategoryDetailItem
SubClassOf
    contractQuantity exactly 1 xsd:decimal,
    contractUnitPrice exactly 1 xsd:decimal,
    contractAmount exactly 1 xsd:decimal
```

---

## A29. 기성내역항목의 수량·금액 정보

하나의 기성내역항목은 계약수량, 전회누계수량, 금회수량, 누계수량, 잔여수량, 계약단가, 계약금액, 전회누계금액, 금회금액, 누계금액 및 잔여금액을 각각 정확히 하나씩 갖는다.

**실제 OWL 구현**

A29는 하나의 개념 공리이지만 실제 OWL 구현에서는 아래 11개의 Datatype Cardinality restriction으로 세분된다.

```text
ProgressPaymentItem
SubClassOf
    contractQuantity exactly 1 xsd:decimal,
    previousCumulativeQuantity exactly 1 xsd:decimal,
    currentQuantity exactly 1 xsd:decimal,
    cumulativeQuantity exactly 1 xsd:decimal,
    remainingQuantity exactly 1 xsd:decimal,
    contractUnitPrice exactly 1 xsd:decimal,
    contractAmount exactly 1 xsd:decimal,
    previousCumulativeAmount exactly 1 xsd:decimal,
    currentAmount exactly 1 xsd:decimal,
    cumulativeAmount exactly 1 xsd:decimal,
    remainingAmount exactly 1 xsd:decimal
```

---

## A30. 계약집계항목의 계약집계금액

하나의 계약집계항목은 정확히 하나의 계약집계금액을 갖는다.

**OWL 구현**

기존 데이터속성 `contractAmount`를 집계항목에 재사용한다.

```text
ContractSummaryItem
SubClassOf
    contractAmount exactly 1 xsd:decimal
```

---

## A31. 기성집계항목의 금회집계금액

하나의 기성집계항목은 정확히 하나의 금회집계금액을 갖는다.

**OWL 구현**

기존 데이터속성 `currentAmount`를 집계항목에 재사용한다.

```text
ProgressPaymentSummaryItem
SubClassOf
    currentAmount exactly 1 xsd:decimal
```

---

# Ⅵ. 비용항목과 공종의 고정 관계

## A32. 철근 비용항목의 공종

철근 비용항목은 철근공사에 속한다.

**Manchester Syntax**

```text
RebarCostItem
SubClassOf
    belongsToWorkCategory value RebarWork
```

---

## A33. 콘크리트 비용항목의 공종

콘크리트 비용항목은 콘크리트공사에 속한다.

**Manchester Syntax**

```text
ConcreteCostItem
SubClassOf
    belongsToWorkCategory value ConcreteWork
```

---

## A34. 거푸집 비용항목의 공종

거푸집 비용항목은 거푸집공사에 속한다.

**Manchester Syntax**

```text
FormworkCostItem
SubClassOf
    belongsToWorkCategory value FormworkWork
```

---

## A35. 동바리 비용항목의 공종

동바리 비용항목은 동바리공사에 속한다.

**Manchester Syntax**

```text
ShoringCostItem
SubClassOf
    belongsToWorkCategory value ShoringWork
```

---

# Ⅶ. 관계의 논리적 특성

## A36. 이전 기성회차의 자기참조 금지

하나의 기성회차는 자기 자신을 이전 기성회차로 가질 수 없다.

`IrreflexiveObjectProperty`

```text
Irreflexive: previousProgressRound
```

---

## A37. 이전 기성회차 관계의 비대칭성

기성회차 A가 기성회차 B를 이전 기성회차로 갖는 경우, 기성회차 B가 동시에 기성회차 A를 이전 기성회차로 가질 수 없다.

예:

```text
3회차 → 이전 기성회차 → 2회차
```

이면 다음은 허용되지 않는다.

```text
2회차 → 이전 기성회차 → 3회차
```

`AsymmetricObjectProperty`

```text
Asymmetric: previousProgressRound
```

---

## A38. 전회누계 전달의 자기참조 금지

하나의 기성내역항목은 자신의 전회누계값을 자기 자신에게서 전달받을 수 없다.

`IrreflexiveObjectProperty`

```text
Irreflexive: providesCumulativeValuesTo
```
