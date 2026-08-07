import type { Locator, Page } from "@playwright/test";

import {
  expect,
  test,
  type MockCandidateApi,
} from "./reference-discovery-candidates.fixtures";

const CANDIDATE_PATH =
  "/api/v1/analyst-references/discovery-candidates";

function candidatePanel(page: Page): Locator {
  return page
    .getByRole("heading", { name: "검토 대기 자료" })
    .locator("xpath=ancestor::section[1]");
}

function candidateCard(panel: Locator, title: string): Locator {
  return panel.locator("article").filter({ hasText: title }).first();
}

async function openSources(
  page: Page,
  mockApi: MockCandidateApi,
): Promise<Locator> {
  await page.goto("/sources");
  const panel = candidatePanel(page);
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("navigation", {
    name: "후보 목록 페이지 이동",
  })).toContainText("전체 48건");
  expect(mockApi.candidateListRequests().length).toBeGreaterThan(0);
  return panel;
}

async function selectAllStatuses(panel: Locator): Promise<void> {
  await panel.getByLabel("검토 상태").selectOption("");
  await expect(
    panel.getByRole("navigation", {
      name: "후보 목록 페이지 이동",
    }),
  ).toContainText("전체 51건");
}

async function openCandidate(
  panel: Locator,
  title: string,
): Promise<Locator> {
  const card = candidateCard(panel, title);
  await card.getByRole("button", { name: "상세 보기" }).click();
  await expect(
    card.getByRole("heading", { name: "후보 상세 정보" }),
  ).toBeVisible();
  return card;
}

async function waitForCandidateRequest(
  mockApi: MockCandidateApi,
  previousCount: number,
): Promise<URLSearchParams> {
  await expect
    .poll(() => mockApi.candidateListRequests().length)
    .toBeGreaterThan(previousCount);
  const request = mockApi.candidateListRequests().at(-1);
  expect(request).toBeDefined();
  return new URLSearchParams(request?.query);
}

test.describe("FRZ-006 candidate review browser QA", () => {
  test("paginates 51 candidates and resets every filter to offset zero", async ({
    page,
    mockApi,
  }) => {
    const panel = await openSources(page, mockApi);
    const pagination = panel.getByRole("navigation", {
      name: "후보 목록 페이지 이동",
    });
    const previous = pagination.getByRole("button", {
      name: "이전 후보 페이지",
    });
    const next = pagination.getByRole("button", {
      name: "다음 후보 페이지",
    });

    await selectAllStatuses(panel);
    await expect(pagination).toContainText(
      "1-50건 표시 / 전체 51건 · 1/2페이지",
    );
    await expect(previous).toBeDisabled();
    await expect(next).toBeEnabled();

    await next.click();
    await expect(pagination).toContainText(
      "51-51건 표시 / 전체 51건 · 2/2페이지",
    );
    await expect(previous).toBeEnabled();
    await expect(next).toBeDisabled();

    await previous.click();
    await expect(pagination).toContainText("1/2페이지");
    await expect(previous).toBeDisabled();

    await next.click();
    let count = mockApi.candidateListRequests().length;
    await panel.getByLabel("공식 출처").selectOption("source-001");
    let query = await waitForCandidateRequest(mockApi, count);
    expect(query.get("offset")).toBe("0");

    await panel.getByLabel("공식 출처").selectOption("");
    await expect(pagination).toContainText("전체 51건");
    await next.click();
    count = mockApi.candidateListRequests().length;
    await panel
      .getByLabel("자동 구독")
      .selectOption("subscription-001");
    query = await waitForCandidateRequest(mockApi, count);
    expect(query.get("offset")).toBe("0");

    await panel.getByLabel("자동 구독").selectOption("");
    await expect(pagination).toContainText("전체 51건");
    await next.click();
    count = mockApi.candidateListRequests().length;
    await panel.getByLabel("검토 상태").selectOption("DATE_UNVERIFIED");
    query = await waitForCandidateRequest(mockApi, count);
    expect(query.get("offset")).toBe("0");

    await panel.getByLabel("검토 상태").selectOption("");
    await expect(pagination).toContainText("전체 51건");
    await next.click();
    count = mockApi.candidateListRequests().length;
    await panel
      .getByLabel("제목·전문가·도메인 검색")
      .fill("second-search");
    await panel.getByRole("button", { name: "검색 적용" }).click();
    query = await waitForCandidateRequest(mockApi, count);
    expect(query.get("offset")).toBe("0");
    expect(query.get("query")).toBe("second-search");
    await expect(panel).toContainText("second-search 최신 결과");
  });

  test("recovers the last valid page after total decreases", async ({
    page,
    mockApi,
  }) => {
    const panel = await openSources(page, mockApi);
    const pagination = panel.getByRole("navigation", {
      name: "후보 목록 페이지 이동",
    });
    await selectAllStatuses(panel);
    await pagination
      .getByRole("button", { name: "다음 후보 페이지" })
      .click();
    await expect(pagination).toContainText("51-51건 표시");

    const count = mockApi.candidateListRequests().length;
    mockApi.candidateTotalCap = 50;
    await panel.getByRole("button", { name: "새로고침" }).click();
    await expect(pagination).toContainText(
      "1-50건 표시 / 전체 50건 · 1/1페이지",
    );

    const recoveryRequests = mockApi.candidateListRequests().slice(count);
    expect(
      recoveryRequests.map(
        (request) => new URLSearchParams(request.query).get("offset"),
      ),
    ).toEqual(["50", "0"]);
  });

  test("opens and closes detail without duplicating the candidate list request", async ({
    page,
    mockApi,
  }) => {
    const panel = await openSources(page, mockApi);
    const listCount = mockApi.requestCount("GET", CANDIDATE_PATH);
    const detailPath = `${CANDIDATE_PATH}/candidate-001`;
    const detailCount = mockApi.requestCount("GET", detailPath);
    const card = await openCandidate(panel, "FRZ 후보 001");

    await expect
      .poll(() => mockApi.requestCount("GET", detailPath))
      .toBe(detailCount + 1);
    expect(mockApi.requestCount("GET", CANDIDATE_PATH)).toBe(listCount);

    await card.getByRole("button", { name: "상세 닫기" }).click();
    await expect(
      card.getByRole("heading", { name: "후보 상세 정보" }),
    ).toHaveCount(0);
    expect(mockApi.requestCount("GET", CANDIDATE_PATH)).toBe(listCount);
    expect(mockApi.requestCount("GET", detailPath)).toBe(detailCount + 1);
  });

  test("verifies and promotes a candidate with history and final read-only UI", async ({
    page,
    mockApi,
  }) => {
    const panel = await openSources(page, mockApi);
    await selectAllStatuses(panel);
    const card = await openCandidate(panel, "FRZ 후보 001");

    await card
      .getByLabel("확인한 발행일·시간")
      .fill("2026-08-04T09:30");
    await card.getByRole("button", { name: "발행일 확인" }).click();
    await expect(card.getByText("DATE_UNVERIFIED → DATE_VERIFIED")).toBeVisible();
    await expect(
      card.getByRole("button", { name: "발행일 수정" }),
    ).toBeVisible();

    const verifyRequest = mockApi.requests.find(
      (request) =>
        request.method === "POST" &&
        request.path === `${CANDIDATE_PATH}/candidate-001/verify-date`,
    );
    expect(verifyRequest?.body).toMatchObject({
      publishedAt: expect.stringMatching(/Z$/),
    });

    await card
      .getByRole("checkbox", { name: /발행일과 공식 출처/ })
      .check();
    await card.getByRole("button", { name: "참고자료 등록" }).click();

    await expect(card.getByText("DATE_VERIFIED → PROMOTED")).toBeVisible();
    expect(mockApi.candidateById("candidate-001").promotedReferenceId).toBe(
      "reference-promoted-candidate-001",
    );
    await expect(
      card.getByText("이 후보는 최종 검토 상태입니다."),
    ).toBeVisible();
    await expect(card.getByLabel("확인한 발행일·시간")).toHaveCount(0);
    await expect(
      card.getByRole("button", { name: "참고자료 등록" }),
    ).toHaveCount(0);
    expect(mockApi.history.get("candidate-001")?.map((item) => item.action)).toEqual([
      "VERIFY_DATE",
      "PROMOTE",
    ]);
  });

  test("dismisses a separate candidate and removes final-state actions", async ({
    page,
    mockApi,
  }) => {
    const panel = await openSources(page, mockApi);
    await selectAllStatuses(panel);
    const card = await openCandidate(panel, "FRZ 후보 002");

    await card.getByLabel("제외 사유 필수").fill("공식 자료 유형이 아님");
    await card
      .getByRole("checkbox", { name: /입력한 사유로 이 후보를/ })
      .check();
    await card.getByRole("button", { name: "검토 제외" }).click();

    await expect(card.getByText("DATE_UNVERIFIED → DISMISSED")).toBeVisible();
    await expect(
      card.getByText("이 후보는 최종 검토 상태입니다."),
    ).toBeVisible();
    await expect(card.getByLabel("제외 사유 필수")).toHaveCount(0);
    await expect(card.getByRole("button", { name: "검토 제외" })).toHaveCount(0);
  });

  test("blocks a double verify submit while showing its loading state", async ({
    page,
    mockApi,
  }) => {
    const panel = await openSources(page, mockApi);
    await selectAllStatuses(panel);
    const card = await openCandidate(panel, "FRZ 후보 001");
    const gate = mockApi.holdAction("verify-date", "candidate-001");
    const path = `${CANDIDATE_PATH}/candidate-001/verify-date`;

    await card
      .getByLabel("확인한 발행일·시간")
      .fill("2026-08-04T10:00");
    const button = card.getByRole("button", { name: "발행일 확인" });
    await button.click();
    await gate.waitForRequest();

    try {
      const loadingButton = card.getByRole("button", {
        name: "확인 처리 중",
      });
      await expect(loadingButton).toBeDisabled();
      await loadingButton.click({ force: true });
      expect(mockApi.requestCount("POST", path)).toBe(1);
    } finally {
      gate.release();
    }

    await gate.waitForCompletion();
    await expect(card.getByText("DATE_UNVERIFIED → DATE_VERIFIED")).toBeVisible();
    await expect(
      card.getByRole("button", { name: "발행일 수정" }),
    ).toBeVisible();
    expect(mockApi.requestCount("POST", path)).toBe(1);
  });

  test("shows a structured 409 conflict without leaking internals or changing state", async ({
    page,
    mockApi,
  }) => {
    const panel = await openSources(page, mockApi);
    await selectAllStatuses(panel);
    const card = await openCandidate(panel, "FRZ 후보 006");

    await card
      .getByLabel("확인한 발행일·시간")
      .fill("2026-08-04T11:00");
    await card.getByRole("button", { name: "발행일 확인" }).click();

    await expect(
      card.getByText(
        "Reference discovery candidate was modified by another review operation.",
      ),
    ).toBeVisible();
    await expect(card).not.toContainText(/sqlite|sqlalchemy|\.db|C:\\/i);
    expect(mockApi.candidateById("candidate-006").verificationStatus).toBe(
      "DATE_UNVERIFIED",
    );
    await expect(
      card.getByRole("button", { name: "발행일 확인" }),
    ).toBeEnabled();
  });

  test("keeps the latest search result when the previous request finishes late", async ({
    page,
    mockApi,
  }) => {
    const panel = await openSources(page, mockApi);
    const search = panel.getByLabel("제목·전문가·도메인 검색");
    const apply = panel.getByRole("button", { name: "검색 적용" });
    const gate = mockApi.holdCandidateQuery("first-search");

    await search.fill("first-search");
    await apply.click();
    await gate.waitForRequest();

    await search.fill("second-search");
    await apply.click();
    await expect(panel.getByText("second-search 최신 결과")).toBeVisible();
    await expect(panel).not.toContainText("first-search 오래된 결과");

    gate.release();
    await gate.waitForCompletion();
    await expect(panel.getByText("second-search 최신 결과")).toBeVisible();
    await expect(
      panel.getByRole("navigation", { name: "후보 목록 페이지 이동" }),
    ).toContainText("전체 1건 · 1/1페이지");

    const searches = mockApi
      .candidateListRequests()
      .map((request) => new URLSearchParams(request.query))
      .filter((query) => query.get("query"));
    expect(searches.map((query) => query.get("query"))).toEqual([
      "first-search",
      "second-search",
    ]);
    expect(searches.map((query) => query.get("offset"))).toEqual(["0", "0"]);
  });

  test("keeps the sources UI inside a 390px viewport", async ({
    page,
    mockApi,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const panel = await openSources(page, mockApi);
    await selectAllStatuses(panel);
    const card = await openCandidate(panel, "FRZ 후보 001");

    const widths = await page.evaluate(() => ({
      documentScrollWidth: document.documentElement.scrollWidth,
      documentClientWidth: document.documentElement.clientWidth,
      bodyScrollWidth: document.body.scrollWidth,
      bodyClientWidth: document.body.clientWidth,
    }));
    expect(widths.documentScrollWidth).toBeLessThanOrEqual(
      widths.documentClientWidth,
    );
    expect(widths.bodyScrollWidth).toBeLessThanOrEqual(widths.bodyClientWidth);

    const pagination = panel.getByRole("navigation", {
      name: "후보 목록 페이지 이동",
    });
    const paginationBox = await pagination.boundingBox();
    expect(paginationBox).not.toBeNull();
    expect(paginationBox?.x).toBeGreaterThanOrEqual(0);
    expect((paginationBox?.x ?? 0) + (paginationBox?.width ?? 0)).toBeLessThanOrEqual(
      390,
    );
    await expect(pagination).toContainText("1-50건 표시");

    for (const label of ["Provider Item ID", "공식 링크"]) {
      const value = card.getByText(label, { exact: true }).locator("..").locator("dd");
      const fits = await value.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      );
      expect(fits).toBe(true);
    }

    const visibleButtons = card.getByRole("button").filter({ visible: true });
    const buttonMetrics = await visibleButtons.evaluateAll((buttons) =>
      buttons.map((button) => ({
        text: button.textContent?.trim() ?? "",
        clientWidth: button.clientWidth,
        scrollWidth: button.scrollWidth,
        height: button.getBoundingClientRect().height,
      })),
    );
    expect(buttonMetrics.length).toBeGreaterThan(0);
    for (const metric of buttonMetrics) {
      expect(metric.scrollWidth, metric.text).toBeLessThanOrEqual(metric.clientWidth);
      expect(metric.height, metric.text).toBeGreaterThan(0);
    }

    const importTrigger = page.getByRole("button", {
      name: "참고자료 링크 등록",
    });
    await importTrigger.click();
    const dialog = page.getByRole("dialog", {
      name: "애널리스트 참고자료 링크 등록",
    });
    const dialogBox = await dialog.boundingBox();
    expect(dialogBox).not.toBeNull();
    expect(dialogBox?.x).toBeGreaterThanOrEqual(0);
    expect(dialogBox?.y).toBeGreaterThanOrEqual(0);
    expect((dialogBox?.x ?? 0) + (dialogBox?.width ?? 0)).toBeLessThanOrEqual(390);
    expect((dialogBox?.y ?? 0) + (dialogBox?.height ?? 0)).toBeLessThanOrEqual(844);
    const hasScrollableContent = await dialog.locator("*").evaluateAll((elements) =>
      elements.some((element) => {
        const style = window.getComputedStyle(element);
        return (
          ["auto", "scroll"].includes(style.overflowY) &&
          element.scrollHeight > element.clientHeight
        );
      }),
    );
    expect(hasScrollableContent).toBe(true);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);

    const menuTrigger = page.getByRole("button", { name: "주 메뉴 열기" });
    await menuTrigger.click();
    await expect(page.getByRole("dialog", { name: "주 메뉴" })).toBeVisible();
    await page
      .getByRole("button", { name: "주 메뉴 닫기" })
      .first()
      .click({ position: { x: 10, y: 100 } });
    await expect(page.getByRole("dialog", { name: "주 메뉴" })).toHaveCount(0);
    await menuTrigger.click();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "주 메뉴" })).toHaveCount(0);
  });

  test("traps dialog keyboard focus and restores its trigger", async ({
    page,
    mockApi,
  }) => {
    await openSources(page, mockApi);
    const trigger = page.getByRole("button", { name: "참고자료 링크 등록" });
    await trigger.focus();
    await page.keyboard.press("Enter");

    const dialog = page.getByRole("dialog", {
      name: "애널리스트 참고자료 링크 등록",
    });
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(dialog.getByLabel("공개 링크")).toBeFocused();

    const first = dialog.getByRole("button", { name: "창 닫기" });
    const last = dialog.getByRole("button", { name: "등록 전 검증" });
    await first.focus();
    await page.keyboard.press("Shift+Tab");
    await expect(last).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(first).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test("moves, traps, and restores focus for mobile navigation", async ({
    page,
    mockApi,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openSources(page, mockApi);
    const trigger = page.getByRole("button", { name: "주 메뉴 열기" });
    await trigger.focus();
    await page.keyboard.press("Enter");

    const menu = page.getByRole("dialog", { name: "주 메뉴" });
    const close = menu.getByRole("button", { name: "주 메뉴 닫기" });
    const lastLink = menu.locator("a[href]").last();
    await expect(menu).toBeVisible();
    await expect(close).toBeFocused();

    await lastLink.focus();
    await page.keyboard.press("Tab");
    await expect(close).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(lastLink).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });
});
