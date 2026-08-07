export type NavigationItem = {
  href: string;
  label: string;
  nested?: boolean;
};

export const navigation: NavigationItem[] = [
  { href: "/dashboard", label: "오늘의 분석" },
  { href: "/portfolio", label: "분석 종목" },
  { href: "/recommendations", label: "종목 관리 방향" },
  { href: "/news", label: "중요 정보" },
  { href: "/disclosures", label: "공식 공시" },
  { href: "/events", label: "통합 사건" },
  { href: "/macro", label: "경제·기업 일정" },
  { href: "/briefings", label: "브리핑" },
  { href: "/settings", label: "개인 설정" },
  { href: "/sources", label: "출처·검증 상태" },
  { href: "/system", label: "시스템 상태", nested: true },
];

export const primaryNavigation = navigation.slice(0, 9);
export const operationalNavigation = navigation.slice(9);
