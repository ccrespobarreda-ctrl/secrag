# Relabelling review

23 labels no longer hold against `data/chunks.json`. For each,
the text the label was written against is shown first, recovered from
`tests/fixture_corpus.json`, and then every chunk of the same document in
the corpus on disk that contains the anchor.

**Nothing is applied from this file until a decision line is filled in.**
An automatic rule that moved each label to its nearest match would inflate
every figure in the project, which is the failure `src/check_neighbours.py`
already refused to commit and `docs/measurement-honesty.md` documents.

Write the chosen index after `Decision:`, or `discard` if the label should
go, or `read` if the chunk has to be opened before deciding. `CERTAIN`
means the candidate's text is identical to the release chunk once
whitespace is flattened, so only the index changed.

---

## Q001 · URBN-10-K-2026 · chunk 121

**Question.** What were Urban Outfitters' total net sales for the fiscal year ended January 31, 2026?

**Anchor.** `6,165,376`

**Labelled answer.** $6,165,376 thousand

**The release chunk, as labelled on 17 August:**

> ... BAN OUTFITTERS, INC. Consolidated Statements of Income (in thousands, except share and per share data) Fiscal Year Ended January 31, 2026 2025 2024 Net sales $ **6,165,376** $ 5,550,666 $ 5,153,237 Cost of sales (excluding store impairment and lease abandonment charges) 3,945,634 3,619,395 3,425,958 Store impairment and lease aband ...

**Candidates in the corpus on disk** (5 chunk(s) contain the anchor):

- **chunk 118** (-3)  **CERTAIN — identical to the release chunk**

  > ... BAN OUTFITTERS, INC. Consolidated Statements of Income (in thousands, except share and per share data) Fiscal Year Ended January 31, 2026 2025 2024 Net sales $ **6,165,376** $ 5,550,666 $ 5,153,237 Cost of sales (excluding store impairment and lease abandonment charges) 3,945,634 3,619,395 3,425,958 Store impairment and lease aband ...

- **chunk 178** (+57)

  > ... Fiscal Year Ended January 31, 2026: Retail Operations Subscription Operations Wholesale Operations Total Company Net sales(1) $ 5,282,676 $ 568,418 $ 314,282 $ **6,165,376** Cost of sales (excluding store impairment)(2) 3,313,849

- **chunk 179** (+58)

  > Retail Operations Subscription Operations Wholesale Operations Total Company Net sales(1) $ 5,282,676 $ 568,418 $ 314,282 $ **6,165,376** Cost of sales (excluding store impairment)(2) 3,313,849 416,363 215,422 3,945,634 Store impairment 1,989 — — 1,989 Segment gross profit 1,966,838 152,055 98,86 ...

- **chunk 182** (+61)

  > ... sories 18,758 6 % 14,727 5 % 17,671 7 % Other 1,123 0 % 1,549 1 % 1,778 1 % Wholesale operations(1) 314,282 100 % 275,578 100 % 238,680 100 % Total net sales $ **6,165,376** $ 5,550,666 $ 5,153,237 (1) Net of intersegment elimination. The Apparel category includes intimates and activewear. The Home category includes home furnishing ...

- **chunk 183** (+62)

  > ... Ended January 31, 2026 2025 2024 Net Sales Domestic operations $ 5,380,595 $ 4,866,286 $ 4,506,805 Foreign operations 784,781 684,380 646,432 Total net sales $ **6,165,376** $ 5,550,666 $ 5,153,237 January 31, 2026 2025 Property and equipment, net Domestic operations $ 1,303,937 $ 1,188,769 Foreign operations 162,299 142,308 Total  ...

**Decision:** 

---

## Q002 · UAA-10-K-2026 · chunk 126

**Question.** What were Under Armour's net revenues in fiscal 2026?

**Anchor.** `(Note 10) $ 4,966,370`

**Labelled answer.** $4,966,370 thousand

**The release chunk, as labelled on 17 August:**

> 2026 2025 2024 Net revenues **(Note 10) $ 4,966,370** $ 5,164,310 $ 5,701,879 Cost of goods sold 2,707,512 2,689,566 3,071,626 Gross profit 2,258,858 2,474,744 2,630,253 Selling, general and administrative expense ...

**Candidates in the corpus on disk** (2 chunk(s) contain the anchor):

- **chunk 122** (-4)

  > ...  of Contents UNDER ARMOUR, INC. CONSOLIDATED STATEMENTS OF OPERATIONS (In thousands, except per share amounts) Year Ended March 31, 2026 2025 2024 Net revenues **(Note 10) $ 4,966,370** $ 5,164,310 $ 5,701,879 Cost of goods sold 2,707,512 2,689,566 3,071,626 Gross profit

- **chunk 123** (-3)  **CERTAIN — identical to the release chunk**

  > 2026 2025 2024 Net revenues **(Note 10) $ 4,966,370** $ 5,164,310 $ 5,701,879 Cost of goods sold 2,707,512 2,689,566 3,071,626 Gross profit 2,258,858 2,474,744 2,630,253 Selling, general and administrative expense ...

**Decision:** 

---

## Q003 · LULU-10-K-2026 · chunk 118

**Question.** How does Lululemon recognize revenue from product sales?

**Anchor.** `transfer of control`

**Labelled answer.** Revenue is recognized when performance obligations are satisfied through the transfer of control. Company-operated store revenue is recognized at the point of sale, while e-commerce and wholesale revenue is recognized upon receipt by the customer.

**The release chunk, as labelled on 17 August:**

> Revenue is recognized when performance obligations are satisfied through the **transfer of control** of promised goods or services to the Company's customers. Control transfers once a customer has the ability to direct the use of, and obtain substantially all  ...

**Candidates in the corpus on disk** (2 chunk(s) contain the anchor):

- **chunk 113** (-5)

  > ... ales taxes collected from customers on behalf of taxing authorities; and •returns. Revenue is recognized when performance obligations are satisfied through the **transfer of control** of promised goods or services to the Company's customers. Control transfers once a customer has the ability to direct the use of, and obtain substantially all  ...

- **chunk 114** (-4)  **CERTAIN — identical to the release chunk**

  > Revenue is recognized when performance obligations are satisfied through the **transfer of control** of promised goods or services to the Company's customers. Control transfers once a customer has the ability to direct the use of, and obtain substantially all  ...

**Decision:** 

---

## Q004 · NKE-10-K-2026 · chunk 85

**Question.** What was Nike's inventory balance at the end of fiscal 2026?

**Anchor.** `7.5`

**Labelled answer.** $7.5 billion

**The release chunk, as labelled on 17 August:**

> ... n fiscal 2026 compared to $46.3 billion in fiscal 2025, flat on a reported basis and down 2% on a currency-neutral basis. •NIKE Brand wholesale revenues were $2**7.5** billion in fiscal 2026 compared to $25.9 billion in fiscal 2025. The increase on a currency-neutral basis was driven by higher revenues in North America, prima ...

**Candidates in the corpus on disk** (4 chunk(s) contain the anchor):

- **chunk 83** (-2)  **CERTAIN — identical to the release chunk**

  > ... n fiscal 2026 compared to $46.3 billion in fiscal 2025, flat on a reported basis and down 2% on a currency-neutral basis. •NIKE Brand wholesale revenues were $2**7.5** billion in fiscal 2026 compared to $25.9 billion in fiscal 2025. The increase on a currency-neutral basis was driven by higher revenues in North America, prima ...

- **chunk 84** (-1)

  > •Inventories as of May 31, 2026 were $**7.5** billion, flat compared to the prior year, primarily reflecting an increase in units, offset by product mix. •We returned approximately $2.5 billion to our shar ...

- **chunk 93** (+8)

  > ... venue growth. Higher ASP per unit was primarily due to product mix, partially offset by higher discounts and channel mix. •NIKE Brand wholesale revenues were $2**7.5** billion in fiscal 2026 compared to $25.9 billion in fiscal 2025, up 6% on a reported basis and up 4% on a currency-neutral basis. The increase on a currency-ne ...

- **chunk 117** (+32)

  > ... e amount authorized for repurchase. As of May 31, 2026, we had repurchased 124.4 million shares at a cost of approximately $12.1 billion (an average price of $9**7.5**7 per share) under this $18 billion share repurchase program. We paused repurchases under this program during the first quarter of fiscal 2026 and no shares wer ...

**Decision:** 

---

## Q005 · CROX-10-K-2025 · chunk 169

**Question.** Which auditor signed Crocs' financial statements?

**Anchor.** `Deloitte`

**Labelled answer.** Deloitte & Touche LLP

**The release chunk, as labelled on 17 August:**

> ...  the mathematical accuracy of the calculation –Developing a range of independent estimates and comparing those to the discount rate selected by management. /s/ **Deloitte** & Touche LLP Denver, Colorado February 12, 2026 We have served as the Company's auditor since 2005. F- 3 Table of Contents CROCS, INC. AND SUBSIDIARIES CONSOLI ...

**Candidates in the corpus on disk** (3 chunk(s) contain the anchor):

- **chunk 147** (-22)

  > ... isk that controls may become inadequate because of changes in conditions, or that the degree of compliance with the policies or procedures may deteriorate. /s/ **Deloitte** & Touche LLP Denver, Colorado February 12, 2026 52 Table of Contents ITEM 9B. Other Information During the three months ended December 31, 2025, no directors o ...

- **chunk 160** (-9)

  > ... ein by reference to Exhibit 19 to Crocs, Inc.’s Annual Report on Form 10-K, filed on February 13, 2025). 21 † Subsidiaries of the registrant. 23.1 † Consent of **Deloitte** & Touche LLP. 31.1 † Certification of the Chief Executive Officer pursuant to Rule 13a-14(a) or Rule 15d-14(a) of the Securities Exchange Act of 1934 as adopte ...

- **chunk 166** (-3)  **CERTAIN — identical to the release chunk**

  > ...  the mathematical accuracy of the calculation –Developing a range of independent estimates and comparing those to the discount rate selected by management. /s/ **Deloitte** & Touche LLP Denver, Colorado February 12, 2026 We have served as the Company's auditor since 2005. F- 3 Table of Contents CROCS, INC. AND SUBSIDIARIES CONSOLI ...

**Decision:** 

---

## Q009 · WRBY-10-K-2025 · chunk 155

**Question.** How many retail stores did Warby Parker operate at the end of the fiscal year?

**Anchor.** `Store Count(1) 323 276 237`

**Labelled answer.** Warby Parker had 323 retail stores as of December 31, 2025.

**The release chunk, as labelled on 17 August:**

> Year Ended December 31, 2025 2024 2023 Active Customers (in thousands) 2,689 2,514 2,332 **Store Count(1) 323 276 237** Adjusted EBITDA(2) (in thousands) $ 95,211 $ 73,111 $ 52,352 Adjusted EBITDA Margin(2) 10.9 % 9.5 % 7.8 % __________________ (1)Store Count number at the end o ...

**Candidates in the corpus on disk** (2 chunk(s) contain the anchor):

- **chunk 152** (-3)

  > ... AAP financial measures for the periods presented, which are unaudited. Year Ended December 31, 2025 2024 2023 Active Customers (in thousands) 2,689 2,514 2,332 **Store Count(1) 323 276 237** Adjusted EBITDA(2) (in thousands) $ 95,211 $ 73,111 $

- **chunk 153** (-2)  **CERTAIN — identical to the release chunk**

  > Year Ended December 31, 2025 2024 2023 Active Customers (in thousands) 2,689 2,514 2,332 **Store Count(1) 323 276 237** Adjusted EBITDA(2) (in thousands) $ 95,211 $ 73,111 $ 52,352 Adjusted EBITDA Margin(2) 10.9 % 9.5 % 7.8 % __________________ (1)Store Count number at the end o ...

**Decision:** 

---

## Q010 · W-10-K-2025 · chunk 151

**Question.** What were Wayfair's total net revenues for the year ended December 31, 2025?

**Anchor.** `data) Net revenue $ 12,457`

**Labelled answer.** $12,457 million

**The release chunk, as labelled on 17 August:**

> CONSOLIDATED STATEMENTS OF OPERATIONS Year Ended December 31, 2025 2024 2023 (in millions, except per share **data) Net revenue $ 12,457** $ 11,851 $ 12,003 Cost of goods sold 8,692 8,277 8,336 Gross profit 3,765 3,574 3,667 Operating expenses: Customer service and merchant fees 471 470 557 Advert ...

**Candidates in the corpus on disk** (2 chunk(s) contain the anchor):

- **chunk 149** (-2)

  > ... ncial statements. 63 Table of Contents WAYFAIR INC. CONSOLIDATED STATEMENTS OF OPERATIONS Year Ended December 31, 2025 2024 2023 (in millions, except per share **data) Net revenue $ 12,457** $ 11,851 $ 12,003 Cost of goods sold 8,692 8,277 8,336 Gross profit

- **chunk 150** (-1)  **CERTAIN — identical to the release chunk**

  > CONSOLIDATED STATEMENTS OF OPERATIONS Year Ended December 31, 2025 2024 2023 (in millions, except per share **data) Net revenue $ 12,457** $ 11,851 $ 12,003 Cost of goods sold 8,692 8,277 8,336 Gross profit 3,765 3,574 3,667 Operating expenses: Customer service and merchant fees 471 470 557 Advert ...

**Decision:** 

---

## Q011 · PTON-10-K-2026 · chunk 138

**Question.** What are Peloton's primary sources of revenue?

**Anchor.** `(collectively, the “Connected`

**Labelled answer.** Suscripciones recurrentes y venta de Connected Fitness Products

**The release chunk, as labelled on 17 August:**

> ... rtfolio of Connected Fitness Products primarily consists of the Peloton Original Series, Peloton Cross Training Series, Peloton Pro Series, and Precor Products **(collectively, the “Connected** Fitness Products”), and related accessories, delivery and installation services, extended warranty and other service agreements, and branded apparel. In Octobe ...

**Candidates in the corpus on disk** (1 chunk(s) contain the anchor):

- **chunk 137** (-1)  **CERTAIN — identical to the release chunk**

  > ... rtfolio of Connected Fitness Products primarily consists of the Peloton Original Series, Peloton Cross Training Series, Peloton Pro Series, and Precor Products **(collectively, the “Connected** Fitness Products”), and related accessories, delivery and installation services, extended warranty and other service agreements, and branded apparel. In Octobe ...

**Decision:** 

---

## Q011 · PTON-10-K-2026 · chunk 145

**Question.** What are Peloton's primary sources of revenue?

**Anchor.** `of Ending Paid Connected`

**Labelled answer.** Suscripciones recurrentes y venta de Connected Fitness Products

**The release chunk, as labelled on 17 August:**

> Average Net Monthly Paid Connected Fitness Subscription Churn To align with the definition **of Ending Paid Connected** Fitness Subscriptions above, our quarterly Average Net Monthly Paid Connected Fitness Subscription Churn is calculated as follows: Paid Connected Fitness Subsc ...

**Candidates in the corpus on disk** (1 chunk(s) contain the anchor):

- **chunk 144** (-1)  **CERTAIN — identical to the release chunk**

  > Average Net Monthly Paid Connected Fitness Subscription Churn To align with the definition **of Ending Paid Connected** Fitness Subscriptions above, our quarterly Average Net Monthly Paid Connected Fitness Subscription Churn is calculated as follows: Paid Connected Fitness Subsc ...

**Decision:** 

---

## Q012 · LULU-10-K-2026 · chunk 100

**Question.** What was Lululemon's inventory balance at fiscal year end?

**Anchor.** `1,700,753`

**Labelled answer.** $1.7 billion ($1,700,753 thousand)

**The release chunk, as labelled on 17 August:**

> ...  February 1, 2026 February 2, 2025 ASSETS Current assets Cash and cash equivalents $ 1,807,202 $ 1,984,336 Accounts receivable, net 190,657 120,173 Inventories **1,700,753** 1,442,081 Prepaid and receivable income taxes 352,469 182,253 Prepaid expenses and other current assets 211,620 251,459 4,262,701 3,980,302 Property and equipm ...

**Candidates in the corpus on disk** (2 chunk(s) contain the anchor):

- **chunk 96** (-4)  **CERTAIN — identical to the release chunk**

  > ...  February 1, 2026 February 2, 2025 ASSETS Current assets Cash and cash equivalents $ 1,807,202 $ 1,984,336 Accounts receivable, net 190,657 120,173 Inventories **1,700,753** 1,442,081 Prepaid and receivable income taxes 352,469 182,253 Prepaid expenses and other current assets 211,620 251,459 4,262,701 3,980,302 Property and equipm ...

- **chunk 126** (+26)

  > ... ons and reserves: Obsolescence provision (52,646) (45,840) Damages provision (34,450) (36,416) Shrink provision (1,727) (1,718) (88,823) (83,974) Inventories $ **1,700,753** $ 1,442,081 Shrink and inventory provision expense was $134.8 million, $139.8 million, and $181.1 million in 2025, 2024, and 2023, respectively. The expense fo ...

**Decision:** 

---

## Q014 · URBN-10-K-2026 · chunk 119

**Question.** Which independent registered public accounting firm audited Urban Outfitters?

**Anchor.** `Deloitte`

**Labelled answer.** Deloitte & Touche LLP

**The release chunk, as labelled on 17 August:**

> ... the mathematical accuracy of the calculation. - Developing a range of independent estimates and comparing those to the fair value determined by management. /s/ **Deloitte** & Touche LLP Philadelphia, Pennsylvania April 1, 2026 We have served as the Company's auditor since 2005. F-3 URBAN OUTFITTERS, INC. Consolidated Balance Sheet ...

**Candidates in the corpus on disk** (6 chunk(s) contain the anchor):

- **chunk 92** (-27)

  > ... isk that controls may become inadequate because of changes in conditions, or that the degree of compliance with the policies or procedures may deteriorate. /s/ **Deloitte** & Touche LLP Philadelphia, Pennsylvania April 1, 2026 35 PART III Item 10. Directors, Executive Officers and Corporate Governance The following table sets fort ...

- **chunk 105** (-14)

  > ... Board of Directors," and "Certain Business Relationships." Item 14. Principal Accountant Fees and Services Our independent registered public accounting firm is **Deloitte** & Touche LLP (PCAOB ID No. 34). Information required by this item is incorporated herein by reference from the Company’s Proxy Statement for the 2026 Annual Me ...

- **chunk 110** (-9)

  > ... reference to Exhibit 19.1 of the Company's Annual Report on Form 10-K (file no. 000-22754) filed on April 1, 2024. 21.1* List of Subsidiaries. 23.1* Consent of **Deloitte** & Touche LLP. 31.1* Rule 13a-14(a)/15d-14(a) Certification of the Company’s Principal Executive Officer. 31.2* Rule 13a-14(a)/15d-14(a) Certification of the Co ...

- **chunk 112** (-7)

  > ... lliken Director April 1, 2026 43 URBAN OUTFITTERS, INC. INDEX TO CONSOLIDATED FINANCIAL STATEMENTS Page Report of Independent Registered Public Accounting Firm—**Deloitte** & Touche LLP F-2 Consolidated Balance Sheets as of January 31, 2026 and January 31, 2025 F-4 Consolidated Statements of Income for the fiscal years ended Janua ...

- **chunk 116** (-3)  **CERTAIN — identical to the release chunk**

  > ... the mathematical accuracy of the calculation. - Developing a range of independent estimates and comparing those to the fair value determined by management. /s/ **Deloitte** & Touche LLP Philadelphia, Pennsylvania April 1, 2026 We have served as the Company's auditor since 2005. F-3 URBAN OUTFITTERS, INC. Consolidated Balance Sheet ...

- **chunk 117** (-2)

  > /s/ **Deloitte** & Touche LLP Philadelphia, Pennsylvania April 1, 2026 We have served as the Company's auditor since 2005. F-3 URBAN OUTFITTERS, INC. Consolidated Balance Sheet ...

**Decision:** 

---

## Q015 · CROX-10-K-2025 · chunk 169

**Question.** What was Crocs' gross profit for fiscal 2025?

**Anchor.** `2,357,055`

**Labelled answer.** $2,357,055 thousand

**The release chunk, as labelled on 17 August:**

> ... pt per share data) Year Ended December 31, 2025 2024 2023 Revenues $ 4,040,647 $ 4,102,108 $ 3,962,347 Cost of sales 1,683,592 1,691,850 1,752,337 Gross profit **2,357,055** 2,410,258 2,210,010 Selling, general and administrative expenses (1) 1,469,425 1,364,265

**Candidates in the corpus on disk** (3 chunk(s) contain the anchor):

- **chunk 101** (-68)

  > ... re data, margin, and average selling price data) Revenues $ 4,040,647 $ 4,102,108 $ (61,461) (1.5) % Cost of sales 1,683,592 1,691,850 8,258 0.5 % Gross profit **2,357,055** 2,410,258 (53,203) (2.2) % Selling, general and administrative expenses 1,469,425 1,364,265 (105,160) (7.7) % Goodwill impairment 307,000 — (307,000) (100.0) % ...

- **chunk 166** (-3)  **CERTAIN — identical to the release chunk**

  > ... pt per share data) Year Ended December 31, 2025 2024 2023 Revenues $ 4,040,647 $ 4,102,108 $ 3,962,347 Cost of sales 1,683,592 1,691,850 1,752,337 Gross profit **2,357,055** 2,410,258 2,210,010 Selling, general and administrative expenses (1) 1,469,425 1,364,265

- **chunk 167** (-2)

  > 1,683,592 1,691,850 1,752,337 Gross profit **2,357,055** 2,410,258 2,210,010 Selling, general and administrative expenses (1) 1,469,425 1,364,265 1,163,940 Goodwill impairment 307,000 — — Asset impairments (1) 431,11 ...

**Decision:** 

---

## Q018 · UAA-10-K-2026 · chunk 217

**Question.** What reportable segments does Under Armour disclose?

**Anchor.** `North America EMEA Asia-Pacific Latin America Total Reportable Segments`

**Labelled answer.** North America, EMEA, Asia-Pacific y Latin America

**The release chunk, as labelled on 17 August:**

> ... scellaneous expenses. Intercompany balances are eliminated in consolidation and are not reviewed when evaluating segment performance. Year Ended March 31, 2026 **North America EMEA Asia-Pacific Latin America Total Reportable Segments** Corporate Other Total Net revenues $ 2,859,420 $ 1,180,510 $ 719,134 $ 234,191 $ 4,993,255 $ (26,885) $ 4,966,370 Less: Marketing and advertising costs 212,677 ...

**Candidates in the corpus on disk** (3 chunk(s) contain the anchor):

- **chunk 214** (-3)  **CERTAIN — identical to the release chunk**

  > ... scellaneous expenses. Intercompany balances are eliminated in consolidation and are not reviewed when evaluating segment performance. Year Ended March 31, 2026 **North America EMEA Asia-Pacific Latin America Total Reportable Segments** Corporate Other Total Net revenues $ 2,859,420 $ 1,180,510 $ 719,134 $ 234,191 $ 4,993,255 $ (26,885) $ 4,966,370 Less: Marketing and advertising costs 212,677 ...

- **chunk 215** (-2)

  > ... million of litigation reserve expense related to the previously disclosed insurance carrier litigation proceedings (refer to Note 8). Year Ended March 31, 2025 **North America EMEA Asia-Pacific Latin America Total Reportable Segments** Corporate Other Total Net revenues $ 3,105,624 $ 1,086,578 $ 755,437 $ 215,427 $ 5,163,066 $ 1,244 $ 5,164,310 Less: Marketing and advertising costs 222,762 12 ...

- **chunk 216** (-1)

  > ... nsolidated Financial Statements in Part II, Item 8 of the Company's Annual Report on Form 10-K for Fiscal 2025). 88 Table of Contents Year ended March 31, 2024 **North America EMEA Asia-Pacific Latin America Total Reportable Segments** Corporate Other Total Net revenues $ 3,505,167 $ 1,081,915 $ 873,019 $ 229,481 $ 5,689,582 $ 12,297 $ 5,701,879 Less: Marketing and advertising costs 252,892 1 ...

**Decision:** 

---

## Q025 · UAA-10-K-2026 · chunk 86

**Question.** How did each of Under Armour's segments perform in fiscal 2026?

**Anchor.** `2,859,420`

**Labelled answer.** Ingresos: North America $2,859,420 (-7.9%), EMEA $1,180,510 (+8.6%), Asia-Pacific $719,134 (-4.8%), Latin America $234,191 (+8.7%). Resultado operativo: North America $442,503 (-29.7%), EMEA $191,487 (+30.1%), Asia-Pacific $84,466 (+15.4%), Latin America $29,901 (-37.1%).

**The release chunk, as labelled on 17 August:**

> ... ith our segments are summarized in the following tables. 34 Table of Contents Net Revenues Year Ended March 31, 2026 2025 Change ($) Change (%) North America $ **2,859,420** $ 3,105,624 $ (246,204) (7.9) % EMEA 1,180,510 1,086,578 93,932 8.6 % Asia-Pacific 719,134 755,437 (36,303) (4.8) % Latin America 234,191 215,427 18,764 8.7 %  ...

**Candidates in the corpus on disk** (2 chunk(s) contain the anchor):

- **chunk 84** (-2)  **CERTAIN — identical to the release chunk**

  > ... ith our segments are summarized in the following tables. 34 Table of Contents Net Revenues Year Ended March 31, 2026 2025 Change ($) Change (%) North America $ **2,859,420** $ 3,105,624 $ (246,204) (7.9) % EMEA 1,180,510 1,086,578 93,932 8.6 % Asia-Pacific 719,134 755,437 (36,303) (4.8) % Latin America 234,191 215,427 18,764 8.7 %  ...

- **chunk 214** (+128)

  > ... ing segment performance. Year Ended March 31, 2026 North America EMEA Asia-Pacific Latin America Total Reportable Segments Corporate Other Total Net revenues $ **2,859,420** $ 1,180,510 $ 719,134 $ 234,191 $ 4,993,255 $ (26,885) $ 4,966,370 Less: Marketing and advertising costs 212,677 123,916 76,973 9,489 423,055 79,235 502,290 Ot ...

**Decision:** 

---

## Q025 · UAA-10-K-2026 · chunk 87

**Question.** How did each of Under Armour's segments perform in fiscal 2026?

**Anchor.** `442,503`

**Labelled answer.** Ingresos: North America $2,859,420 (-7.9%), EMEA $1,180,510 (+8.6%), Asia-Pacific $719,134 (-4.8%), Latin America $234,191 (+8.7%). Resultado operativo: North America $442,503 (-29.7%), EMEA $191,487 (+30.1%), Asia-Pacific $84,466 (+15.4%), Latin America $29,901 (-37.1%).

**The release chunk, as labelled on 17 August:**

> ... d to revenues generated by entities within our operating segments. Operating Income (Loss) Year Ended March 31, 2026 2025 Change ($) Change (%) North America $ **442,503** $ 629,518 $ (187,015) (29.7) % EMEA 191,487 147,182 44,305 30.1 % Asia-Pacific 84,466 73,187 11,279 15.4 % Latin America 29,901 47,532 (17,631) (37.1) % Corpor ...

**Candidates in the corpus on disk** (3 chunk(s) contain the anchor):

- **chunk 85** (-2)  **CERTAIN — identical to the release chunk**

  > ... d to revenues generated by entities within our operating segments. Operating Income (Loss) Year Ended March 31, 2026 2025 Change ($) Change (%) North America $ **442,503** $ 629,518 $ (187,015) (29.7) % EMEA 191,487 147,182 44,305 30.1 % Asia-Pacific 84,466 73,187 11,279 15.4 % Latin America 29,901 47,532 (17,631) (37.1) % Corpor ...

- **chunk 214** (+127)

  > ... 916 76,973 9,489 423,055 79,235 502,290 Other segment expenses(1) 2,204,240 865,107 557,695 194,801 3,821,843 805,349 4,627,192 Total operating income (loss) $ **442,503** $ 191,487 $ 84,466 $ 29,901 $

- **chunk 215** (+128)

  > 865,107 557,695 194,801 3,821,843 805,349 4,627,192 Total operating income (loss) $ **442,503** $ 191,487 $ 84,466 $ 29,901 $ 748,357 $ (911,469) $ (163,112) Interest income (expense), net (30,288) Other income (expense), net (7,276) Income (loss) before  ...

**Decision:** 

---

## Q027 · GAP-10-K-2026 · chunk 57

**Question.** How did Gap's individual brands perform during the fiscal year?

**Anchor.** `follows: Fiscal Year 2025`

**Labelled answer.** Fiscal 2025 comparable sales were Old Navy Global +3%, Gap Global +6%, Banana Republic Global +3% and Athleta Global -9%. Fiscal 2025 net sales were $8,657 million for Old Navy, $3,501 million for Gap, $1,916 million for Banana Republic and $1,219 million for Athleta.

**The release chunk, as labelled on 17 August:**

> ... eve a consistent basis for comparison. 26 The percentage change in Comp Sales by global brand and for The Gap, Inc., as compared with the preceding year, is as **follows: Fiscal Year 2025** 2024 Old Navy Global 3 % 3 % Gap Global 6 % 4 % Banana Republic Global 3 % 1 % Athleta Global (9) % — % The Gap, Inc. 3 % 3 % Store count, net openings/closing ...

**Candidates in the corpus on disk** (1 chunk(s) contain the anchor):

- **chunk 55** (-2)  **CERTAIN — identical to the release chunk**

  > ... eve a consistent basis for comparison. 26 The percentage change in Comp Sales by global brand and for The Gap, Inc., as compared with the preceding year, is as **follows: Fiscal Year 2025** 2024 Old Navy Global 3 % 3 % Gap Global 6 % 4 % Banana Republic Global 3 % 1 % Athleta Global (9) % — % The Gap, Inc. 3 % 3 % Store count, net openings/closing ...

**Decision:** 

---

## Q027 · GAP-10-K-2026 · chunk 102

**Question.** How did Gap's individual brands perform during the fiscal year?

**Anchor.** `channel for fiscal 2025,`

**Labelled answer.** Fiscal 2025 comparable sales were Old Navy Global +3%, Gap Global +6%, Banana Republic Global +3% and Athleta Global -9%. Fiscal 2025 net sales were $8,657 million for Old Navy, $3,501 million for Gap, $1,916 million for Banana Republic and $1,219 million for Athleta.

**The release chunk, as labelled on 17 August:**

> ... handise; the distribution center or store from which the products were shipped; or the region of the franchise or licensing partner. Net sales disaggregated by **channel for fiscal 2025,** 2024, and 2023 are as follows: Fiscal Year ($ in millions) 2025 2024 2023 (2) Store and franchise sales $ 9,385 $ 9,332 $ 9,346 Online sales (1) 5,981 5,754 5, ...

**Candidates in the corpus on disk** (1 chunk(s) contain the anchor):

- **chunk 99** (-3)  **CERTAIN — identical to the release chunk**

  > ... handise; the distribution center or store from which the products were shipped; or the region of the franchise or licensing partner. Net sales disaggregated by **channel for fiscal 2025,** 2024, and 2023 are as follows: Fiscal Year ($ in millions) 2025 2024 2023 (2) Store and franchise sales $ 9,385 $ 9,332 $ 9,346 Online sales (1) 5,981 5,754 5, ...

**Decision:** 

---

## Q028 · W-10-K-2025 · chunk 165

**Question.** What does Wayfair disclose about its logistics and delivery network?

**Anchor.** `Costs: Wayfair`

**Labelled answer.** La red logistica de Wayfair consta de CastleGate y la Wayfair Delivery Network (WDN), mas CastleGate Forwarding para servicios de entrada. CastleGate permite a los proveedores posicionar inventario por adelantado en sus almacenes, con entrega en dos dias o menos a la mayoria de la poblacion de EE UU ...

**The release chunk, as labelled on 17 August:**

> 72 Table of Contents Cost of Goods Sold Costs of goods sold consists of: Product **Costs: Wayfair** capitalizes into inventory the price paid to suppliers for products purchased by Wayfair, direct and indirect labor costs, rent, depreciation and inbound shipp ...

**Candidates in the corpus on disk** (1 chunk(s) contain the anchor):

- **chunk 164** (-1)  **CERTAIN — identical to the release chunk**

  > 72 Table of Contents Cost of Goods Sold Costs of goods sold consists of: Product **Costs: Wayfair** capitalizes into inventory the price paid to suppliers for products purchased by Wayfair, direct and indirect labor costs, rent, depreciation and inbound shipp ...

**Decision:** 

---

## Q029 · ANF-10-K-2026 · chunk 83

**Question.** What tariff and trade risks does Abercrombie & Fitch identify, and what mitigation does it describe?

**Anchor.** `negatively impacted operating income by $90 million or 170 basis points`

**Labelled answer.** Abercrombie identifies tariff risk because a predominant portion of its merchandise is manufactured outside the U.S.; retaliatory tariffs can also disrupt global trade. Mitigation includes managing product costs, reducing operating expenses and pursuing average unit retail growth. Tariffs reduced Fi ...

**The release chunk, as labelled on 17 August:**

> After factoring in certain mitigation strategies, tariffs on goods imported into the U.S. under trade policies in effect through January 31, 2026 **negatively impacted operating income by $90 million or 170 basis points** as a percent of net sales, during Fiscal 2025. Assuming the estimated impact from the tariffs on goods imported into the U.S., including the impact of a 15% ta ...

**Candidates in the corpus on disk** (2 chunk(s) contain the anchor):

- **chunk 79** (-4)

  > ... increase AUR. After factoring in certain mitigation strategies, tariffs on goods imported into the U.S. under trade policies in effect through January 31, 2026 **negatively impacted operating income by $90 million or 170 basis points** as a percent of net sales, during Fiscal 2025. Assuming the estimated impact from the tariffs on goods imported into the U.S., including the impact of a 15% ta ...

- **chunk 80** (-3)  **CERTAIN — identical to the release chunk**

  > After factoring in certain mitigation strategies, tariffs on goods imported into the U.S. under trade policies in effect through January 31, 2026 **negatively impacted operating income by $90 million or 170 basis points** as a percent of net sales, during Fiscal 2025. Assuming the estimated impact from the tariffs on goods imported into the U.S., including the impact of a 15% ta ...

**Decision:** 

---

## Q030 · HNST-10-K-2025 · chunk 172

**Question.** What does Honest Company say about its product categories and its channel mix?

**Anchor.** `third-party ecommerce sites and, prior to December 31, 2025, Honest.com`

**Labelled answer.** Categorias: wipes, personal care, diapers y beauty. Canal: venta a traves de retailers y sus websites, third-party ecommerce sites y, antes del 31 de diciembre de 2025, Honest.com. Desde esa fecha Honest.com dejo de ser un canal de shipping/fulfillment.

**The release chunk, as labelled on 17 August:**

> ...  operations. Components of Results of Operations Revenue We generate revenue through the sale of our products through our leading retailers and their websites, **third-party ecommerce sites and, prior to December 31, 2025, Honest.com**. Our revenue is recognized net of allowances for returns, discounts, credits and any taxes collected from consumers. Cost of Revenue Cost of revenue includes t ...

**Candidates in the corpus on disk** (1 chunk(s) contain the anchor):

- **chunk 171** (-1)  **CERTAIN — identical to the release chunk**

  > ...  operations. Components of Results of Operations Revenue We generate revenue through the sale of our products through our leading retailers and their websites, **third-party ecommerce sites and, prior to December 31, 2025, Honest.com**. Our revenue is recognized net of allowances for returns, discounts, credits and any taxes collected from consumers. Cost of Revenue Cost of revenue includes t ...

**Decision:** 

---

## Q032 · LULU-10-K-2026 · chunk 117

**Question.** Do both Lululemon and Nike report a direct-to-consumer channel?

**Anchor.** `locations, and lululemon`

**Labelled answer.** Yes. Lululemon reports company-operated store and e-commerce net revenue as direct sales channels, while Nike reports NIKE Direct operations, comprised of Nike-owned retail stores and digital platforms.

**The release chunk, as labelled on 17 August:**

> ... upply arrangement net revenue, which consists of royalties as well as sales of the Company's products to licensees, re-commerce revenue, revenue from temporary **locations, and lululemon** Studio revenue from digital content subscriptions. All revenue is reported net of: •markdowns and discounts, •sales taxes collected from customers on behalf of ...

**Candidates in the corpus on disk** (1 chunk(s) contain the anchor):

- **chunk 113** (-4)  **CERTAIN — identical to the release chunk**

  > ... upply arrangement net revenue, which consists of royalties as well as sales of the Company's products to licensees, re-commerce revenue, revenue from temporary **locations, and lululemon** Studio revenue from digital content subscriptions. All revenue is reported net of: •markdowns and discounts, •sales taxes collected from customers on behalf of ...

**Decision:** 

---

## Q035 · CROX-10-K-2025 · chunk 169

**Question.** Which reports higher net revenues, Crocs or Deckers Outdoor?

**Anchor.** `4,040,647`

**Labelled answer.** Deckers Outdoor, con $5,472,296 miles frente a los $4,040,647 miles de Crocs. Deckers cierra el ejercicio el 31 de marzo de 2026 y Crocs el 31 de diciembre de 2025, por lo que los periodos no son identicos.

**The release chunk, as labelled on 17 August:**

> ... ents CROCS, INC. AND SUBSIDIARIES CONSOLIDATED STATEMENTS OF OPERATIONS (in thousands, except per share data) Year Ended December 31, 2025 2024 2023 Revenues $ **4,040,647** $ 4,102,108 $ 3,962,347 Cost of sales 1,683,592 1,691,850 1,752,337 Gross profit 2,357,055 2,410,258 2,210,010 Selling, general and administrative expenses (1) ...

**Candidates in the corpus on disk** (6 chunk(s) contain the anchor):

- **chunk 101** (-68)

  > ...  Change % Change Favorable (Unfavorable) 2025 2024 2025-2024 2025-2024 (in thousands, except per share data, margin, and average selling price data) Revenues $ **4,040,647** $ 4,102,108 $ (61,461) (1.5) % Cost of sales 1,683,592 1,691,850 8,258 0.5 % Gross profit 2,357,055 2,410,258 (53,203) (2.2) % Selling, general and administrat ...

- **chunk 103** (-66)

  > ... 25 456,472 (26.3) % (26.5) % Direct-to-consumer 378,515 367,669 2.9 % 2.8 % Total HEYDUDE Brand 714,840 824,141 (13.3) % (13.5) % Total consolidated revenues $ **4,040,647** $ 4,102,108 (1.5) % (1.7) % (1) Reflects year over year change as if the current period results were in constant currency, which is a non-GAAP financial measur ...

- **chunk 111** (-58)

  > ... ands) Revenues: Crocs Brand revenues $ 3,325,807 $ 3,277,967 1.5 % 1.3 % HEYDUDE Brand revenues 714,840 824,141 (13.3) % (13.5) % Total consolidated revenues $ **4,040,647** $ 4,102,108 (1.5) % (1.7) % Income from operations: Crocs Brand income from operations $ 1,111,679 $ 1,182,012 (6.0) % (5.7) % HEYDUDE Brand income from operat ...

- **chunk 166** (-3)  **CERTAIN — identical to the release chunk**

  > ... ents CROCS, INC. AND SUBSIDIARIES CONSOLIDATED STATEMENTS OF OPERATIONS (in thousands, except per share data) Year Ended December 31, 2025 2024 2023 Revenues $ **4,040,647** $ 4,102,108 $ 3,962,347 Cost of sales 1,683,592 1,691,850 1,752,337 Gross profit 2,357,055 2,410,258 2,210,010 Selling, general and administrative expenses (1) ...

- **chunk 217** (+48)

  > ... and: Wholesale 336,325 456,472 566,937 Direct-to-consumer 378,515 367,669 382,456 Total HEYDUDE Brand (2) 714,840 824,141 949,393 Total consolidated revenues $ **4,040,647** $ 4,102,108 $ 3,962,347 (1) North America includes the United States and Canada. (2) The vast majority of HEYDUDE Brand revenues are derived from North America ...

- **chunk 239** (+70)

  > ...  31, 2025 2024 2023 (in thousands) Location: United States $ 2,260,656 $ 2,482,218 $ 2,573,663 International (1) 1,779,518 1,619,890 1,388,684 Total revenues $ **4,040,647** $ 4,102,108 $ 3,962,347 (1) No individual international country represented 10% or more of consolidated revenues in any of the years presented. The following t ...

**Decision:** 

---

## Q059 · W-10-K-2025 · chunk 106

**Question.** As of December 31, 2025, how many active customers did Wayfair have, and what percentage of orders came from repeat buyers during the year?

**Anchor.** `21 million active customers and during the year ended December 31, 2025, 80.3% of orders came from repeat buyers`

**Labelled answer.** 21 million active customers, and 80.3% of orders came from repeat buyers.

**The release chunk, as labelled on 17 August:**

> ... 1 Table of Contents During the year ended December 31, 2025, net revenue increased by 5.1% compared to the same period in 2024. As of December 31, 2025, we had **21 million active customers and during the year ended December 31, 2025, 80.3% of orders came from repeat buyers**. The increased sales represents our ongoing execution of business initiatives amid persistent macroeconomic pressures on consumers. We also continued to manage ...

**Candidates in the corpus on disk** (1 chunk(s) contain the anchor):

- **chunk 105** (-1)  **CERTAIN — identical to the release chunk**

  > ... 1 Table of Contents During the year ended December 31, 2025, net revenue increased by 5.1% compared to the same period in 2024. As of December 31, 2025, we had **21 million active customers and during the year ended December 31, 2025, 80.3% of orders came from repeat buyers**. The increased sales represents our ongoing execution of business initiatives amid persistent macroeconomic pressures on consumers. We also continued to manage ...

**Decision:** 

---

## Summary

- 23 labels to decide
- 23 candidate(s) byte-identical to the release chunk
- 0 label(s) with no identical candidate, which need the filing opened

When the decisions are written, `python apply_relabel.py` reads this file
and changes only the labels with a decision. Then re-run
`python src/verify_labels.py --questions eval/questions_vnext.yaml --max-anchor-matches 8 --max-exceptions 4`,
rebuild the fixture with `python tests/fixture.py --build`, and re-measure
retrieval. The published 0.735 was measured against the labels as they
were; a new figure has to be published as a new figure.
