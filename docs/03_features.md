# 03. 주요 기능

## 기능 구성

Investment AI Radar는 **종목 관리 → 정보 수집·등록 → 검토 → 사건 연결 → 일정·브리핑 → 사용자 판단** 흐름을 중심으로 구성했습니다.

## 전체 대시보드

<p align="center">
  <img src="images/01_오늘의_분석.png" alt="오늘의 분석" width="100%">
</p>

오늘의 분석 화면에서 종목별 중요 정보, 일정, 브리핑과 관리 상태를 한 흐름으로 확인합니다.

## 1. 분석 종목

- 종목 등록·조회·수정
- 자산 유형과 시장 구분
- 보유·관심·재진입 관심·청산 완료 상태
- 종목 상세 분석
- 다음 확인 일정 연결

<p align="center">
  <img src="images/02_분석_종목_목록.png" alt="분석 종목 목록" width="100%">
</p>

<p align="center">
  <img src="images/03_마이크로소프트_종목_상세_분석.png" alt="종목 상세 분석" width="100%">
</p>

### 동작 확인

**분석 종목 등록**

https://github.com/user-attachments/assets/a3a92ce7-66c1-47dd-945c-cf3e0b8aa2ea

**분석 종목 수정·관리 방향**

https://github.com/user-attachments/assets/1220ae1a-3450-4676-92ac-285f3b4624ab
## 2. 거래 기록

- 매수·매도 거래 기록
- 과거 거래 입력
- 거래 수정과 soft void
- 보유 수량·평균단가 replay
- 매도 원가와 실현손익 계산
- 중복·잘못된 상태 전이 보호

### 동작 확인

https://github.com/user-attachments/assets/d06a5f1f-d0ae-4a06-9506-93588540bfa0
## 3. 공식 출처와 구독

- 기관·회사 공식 출처 등록
- 출처 설정 변경
- 관심 기관·전문가 자동 확인 대상 관리
- 구독 변경 이력
- 공개 참고자료 자동 발견 후보 관리

<p align="center">
  <img src="images/11_출처_검증_상태_공식_출처_관리.png" alt="공식 출처 관리" width="100%">
</p>

<p align="center">
  <img src="images/11_1_출처_검증_상태_자동_구독_검토_대기.png" alt="자동 구독 검토 대기" width="100%">
</p>

### 동작 확인

**공식 출처 등록·수정**

https://github.com/user-attachments/assets/67778e6e-8d7a-4a82-85c1-6073e39431d5

**출처 수정·관심 대상 등록**

https://github.com/user-attachments/assets/f72174c1-d4f8-4341-97de-b0b5d37551eb
## 4. 참고자료

- 애널리스트·전문가 공개 참고자료 직접 등록
- URL, 제목, 발행일, 저자·기관 메타데이터
- Portfolio 연결
- 참고자료 보관함
- 자동 발견 자료와 직접 등록 자료 분리

<p align="center">
  <img src="images/11_2_출처_검증_상태_참고자료_보관함.png" alt="참고자료 보관함" width="100%">
</p>

### 동작 확인

https://github.com/user-attachments/assets/70687ec5-d306-46ba-b42c-085956407c8c
## 5. 검토 대기 자료

- 자동 발견 후보 staging
- 발행일·출처 확인
- 정식 참고자료 승격
- 검토 제외와 제외 사유
- 최종 상태 보호
- 중복 제출과 409 충돌 처리
- pagination과 검색

### 동작 확인

https://github.com/user-attachments/assets/f893039b-4ba2-4cf0-80c3-9d0786bb8f24
## 6. 중요 정보

- URL 기반 등록 전 확인
- URL 정규화와 중복 검사
- 출처 분류
- 종목 연결
- Claim과 Information Event 생성
- 기사 전문 미저장

<p align="center">
  <img src="images/05_중요_정보_검증_상태.png" alt="중요 정보 검증 상태" width="100%">
</p>

### 동작 확인

https://github.com/user-attachments/assets/5b24c288-5dd2-4ff8-a7e8-82fb3ce73cd6
## 7. 공식 공시

- SEC 등 공식 원문 URL 등록
- 공시 유형·발행 시각 확인
- 종목 연결
- 통합 사건 후보 연결
- 공식 원문 링크 유지

<p align="center">
  <img src="images/06_공식_공시.png" alt="공식 공시" width="100%">
</p>

### 동작 확인

https://github.com/user-attachments/assets/36be6be4-660a-4154-9216-a37db2c33f6e
## 8. 통합 사건

- 반복 보도와 공식 자료를 사건 단위로 묶음
- 뉴스 참조·독립 원출처·공식 자료 수 표시
- 검토 상태와 공식 확인 상태 표시

<p align="center">
  <img src="images/07_통합_사건.png" alt="통합 사건" width="100%">
</p>

### 동작 확인

중요 정보와 공식 공시가 통합 사건에 연결되는 흐름은 08·09 검증 영상에서 함께 확인했습니다.

https://github.com/user-attachments/assets/5b24c288-5dd2-4ff8-a7e8-82fb3ce73cd6

https://github.com/user-attachments/assets/36be6be4-660a-4154-9216-a37db2c33f6e
## 9. 경제·기업 일정

- 공식 발표 일정 URL 등록
- timezone-aware 시각
- 종목 연결
- 예상 영향 경로
- 발표 전 확인 목록
- 중복 일정 방지

<p align="center">
  <img src="images/08_경제_기업_일정.png" alt="경제·기업 일정" width="100%">
</p>

### 동작 확인

https://github.com/user-attachments/assets/1b25540b-290d-4db7-94a7-6c90791b1532
## 10. 변경 기반 브리핑

- 기간·중요도 조건 설정
- Preview와 Final 생성 분리
- 중복 상태 fingerprint 제외
- 중요 변경·공식 확인 수 표시
- 이메일 발송 로직과 브리핑 생성을 분리

<p align="center">
  <img src="images/09_변경_기반_브리핑.png" alt="변경 기반 브리핑" width="100%">
</p>

### 동작 확인

https://github.com/user-attachments/assets/4f80dd16-6d9e-4f00-9ec8-0b2474f8c593
## 11. 위험 기준과 관리 방향

- 규칙 기반 위험 기준 제안
- 사용자 확인 후 적용
- 종목 관리 방향 준비 상태
- 데이터 부족·미설정 항목 명시
- 매수·매도 명령, 목표가, 손절가, 상승 확률을 자동 생성하지 않음

<p align="center">
  <img src="images/04_종목_관리_방향_준비_상태.png" alt="종목 관리 방향 준비 상태" width="100%">
</p>

<p align="center">
  <img src="images/10_위험_설정_자동_제안.png" alt="위험 설정 자동 제안" width="100%">
</p>

### 동작 확인

https://github.com/user-attachments/assets/e6edabda-a369-4837-9be1-042f6468e4e5
## 12. 개인 설정

- 국내장·NASDAQ 개장 전/마감 후 브리핑 offset
- 즉시 알림·종합본 조건
- 포함 대상 설정
- 이메일 설정과 최소 중요도
- 시간대 설정

<p align="center">
  <img src="images/10_1_시장_브리핑_알림_설정.png" alt="시장 브리핑 알림 설정" width="100%">
</p>

### 동작 확인

https://github.com/user-attachments/assets/1888abf3-2f54-47e6-bd9c-e25ddcd28db2
## 13. 운영 상태

- 출처·검증 상태
- Provider 연결 상태
- 데이터베이스 상태
- 브리핑·자동화 상태
- 비활성·미설정 기능의 명시적 표시

<p align="center">
  <img src="images/12_시스템_연결_상태.png" alt="시스템 연결 상태" width="100%">
</p>

### 동작 확인

https://github.com/user-attachments/assets/1888abf3-2f54-47e6-bd9c-e25ddcd28db2
## 기능 검증

13개 주요 사용자 시나리오는 실제 UI에서 순서대로 실행해 동작을 확인했습니다.

영상별 검증 항목과 결과는 [05. Validation](05_validation.md)에 정리했습니다.

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
