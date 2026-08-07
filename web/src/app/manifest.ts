import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "개인 투자·시장정보 AI 레이더",
    short_name: "AI 레이더",
    description: "사용자 1명 전용 비공개 투자·시장정보 조사 서비스",
    start_url: "/dashboard",
    display: "standalone",
    background_color: "#080D18",
    theme_color: "#0D1423",
  };
}
