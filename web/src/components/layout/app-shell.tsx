"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  operationalNavigation,
  primaryNavigation,
  type NavigationItem,
} from "@/config/navigation";
import { getProviderStatus } from "@/lib/api/providers";

function NavigationLink({
  href,
  label,
  nested,
  onNavigate,
}: NavigationItem & { onNavigate?: () => void }) {
  const pathname = usePathname();
  const active = pathname === href;
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={`flex min-h-11 items-center rounded-xl border text-sm font-semibold ${
        nested ? "ml-5 px-4" : "px-3"
      } ${
        active
          ? "border-cyan/40 bg-cyan/10 text-cyan"
          : "border-transparent text-secondary hover:border-border hover:bg-card"
      }`}
    >
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [collectionLabel, setCollectionLabel] = useState("수집 상태 확인 중");
  const menuTriggerRef = useRef<HTMLButtonElement>(null);
  const menuPanelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    getProviderStatus(controller.signal)
      .then((result) => {
        const official = result.items.filter((item) =>
          ["OPENDART", "SEC_EDGAR"].includes(item.provider),
        );
        const ready = official.filter((item) => item.status === "READY").length;
        const configured = official.filter((item) => item.configured).length;
        setCollectionLabel(
          ready === official.length && ready > 0
            ? "수집 정상"
            : ready > 0
              ? "공식 공시 연결됨"
              : configured > 0
                ? "일부 출처 연결"
                : "수집 미설정",
        );
      })
      .catch(() => setCollectionLabel("수집 상태 확인 필요"));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const previousOverflow = document.body.style.overflow;
    const menuTrigger = menuTriggerRef.current;
    document.body.style.overflow = "hidden";
    const focusableSelector =
      "button:not([disabled]), a[href], input:not([disabled]), " +
      "select:not([disabled]), textarea:not([disabled]), " +
      "[tabindex]:not([tabindex='-1'])";
    menuPanelRef.current
      ?.querySelector<HTMLElement>(focusableSelector)
      ?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setMenuOpen(false);
        return;
      }
      if (event.key !== "Tab") return;

      const focusable =
        menuPanelRef.current?.querySelectorAll<HTMLElement>(
          focusableSelector,
        );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
      menuTrigger?.focus();
    };
  }, [menuOpen]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b border-border bg-surface/95 backdrop-blur">
        <div className="mx-auto flex min-h-17 max-w-[1600px] items-center justify-between gap-3 px-4 md:px-6">
          <div className="min-w-0">
            <p className="truncate text-base font-bold tracking-tight md:text-lg">
              개인 투자·시장정보 AI 레이더
            </p>
            <p className="text-xs text-muted">
              Investment AI Radar · 투자 정보 수집·검증·관리
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <div
              className="rounded-full border border-border bg-card px-3 py-2 text-xs text-secondary"
              aria-label="시스템 데이터 상태"
            >
              {collectionLabel}
            </div>
            <button
              ref={menuTriggerRef}
              type="button"
              aria-label="주 메뉴 열기"
              aria-expanded={menuOpen}
              aria-controls="mobile-navigation"
              onClick={() => setMenuOpen(true)}
              className="grid size-11 place-items-center rounded-xl border border-border text-xl md:hidden"
            >
              ☰
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px]">
        <aside className="sticky top-17 hidden h-[calc(100vh-4.25rem)] w-64 shrink-0 border-r border-border bg-surface p-4 md:block">
          <nav aria-label="주 메뉴" className="space-y-1">
            {primaryNavigation.map((item) => (
              <NavigationLink key={item.href} {...item} />
            ))}
            <p className="px-3 pb-1 pt-4 text-xs font-bold text-muted">
              운영 메뉴
            </p>
            {operationalNavigation.map((item) => (
              <NavigationLink key={item.href} {...item} />
            ))}
          </nav>
          <p className="absolute bottom-5 left-4 right-4 text-xs leading-5 text-muted">
            정보 조사 도구이며 주문을 실행하지 않습니다.
          </p>
        </aside>

        <main className="min-w-0 flex-1 px-4 pb-10 pt-6 md:px-8 md:pt-8">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>

      {menuOpen ? (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            aria-label="주 메뉴 닫기"
            onClick={() => setMenuOpen(false)}
            className="absolute inset-0 bg-black/70"
          />
          <aside
            ref={menuPanelRef}
            id="mobile-navigation"
            role="dialog"
            aria-modal="true"
            aria-label="주 메뉴"
            className="absolute inset-y-0 right-0 flex w-[min(88vw,22rem)] flex-col border-l border-border bg-surface shadow-2xl"
          >
            <div className="flex min-h-17 items-center justify-between border-b border-border px-4">
              <p className="font-bold">전체 메뉴</p>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                aria-label="주 메뉴 닫기"
                className="grid size-11 place-items-center rounded-xl border border-border text-xl"
              >
                ×
              </button>
            </div>
            <nav
              aria-label="모바일 주 메뉴"
              className="min-h-0 flex-1 space-y-1 overflow-y-auto p-4"
            >
              {primaryNavigation.map((item) => (
                <NavigationLink
                  key={item.href}
                  {...item}
                  onNavigate={() => setMenuOpen(false)}
                />
              ))}
              <p className="px-3 pb-1 pt-4 text-xs font-bold text-muted">
                운영 메뉴
              </p>
              {operationalNavigation.map((item) => (
                <NavigationLink
                  key={item.href}
                  {...item}
                  onNavigate={() => setMenuOpen(false)}
                />
              ))}
            </nav>
            <p className="border-t border-border px-4 py-4 text-xs leading-5 text-muted">
              정보 조사 도구이며 주문을 실행하지 않습니다.
            </p>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
