# team_cycle_station
목표 : 은평구 따릉이 스테이션 데이터를 분석하여 수요 패턴을 파악하고,
이를 바탕으로 따릉이 수요 예측 앱을 개발한다.


## 진행 프로세스
1. 은평구에 위치한 따릉이 스테이션 데이터를 분석해서 10개의 군집으로 나눔 -> 12개로 변경.
2. 각 팀원은 담당 군집 1개를 선택하고, 해당 군집 내 스테이션 3개를 선정하여 입지/이용 패턴/주변 특성 등을 분석한다. 
- 2026.03.13

## 기본 데이터 프레임 불러와서 사용. (파일명 : 정류장정보_시간대별_합친것.csv)
압축 파일 읽기 df = pd.read_parquet("data.parquet")

## git 작업 규칙
###########################################################
- 본인의 이름으로 branch 만들어서 본인 branch에서만 작업 해주세요.
- main push를 하게 될 시에는 꼭 언급해주세요.
###########################################################
### git rule (분석 파일 작업시)
- 작업용 노트북 파일은 `note` 폴더 안에 본인 이름으로 생성해주세요.
  - 예: `lsh.ipynb`
- 본인 파일이 아닌 `.ipynb` 파일은 수정하지 않습니다.
- `Data` 폴더에는 무작위 파일을 넣지 말고, 필요 없는 파일은 사용 후 삭제해주세요.
- 파일이 섞이지 않도록 폴더 구조를 유지해주세요.


### git rule(flutter 작업시)
- 작업 시작 전 항상 최신 상태로 `pull` 후 작업해주세요.
- 충돌(conflict) 발생 시 본인이 우선 해결하고, 해결이 어려우면 팀원에게 바로 공유해주세요.
- `push` 전에는 반드시 `pull request`를 생성해주세요.
- PR 생성 후 팀원에게 꼭 알려주세요.
- 공용 파일 수정이 필요한 경우, 수정 전에 먼저 공유해주세요.


## 시작 파일
### Data : 
- 은평구_스테이션_군집화_1차 : 1차 군집화 작업 결과,
- 은평_분기별_대여소_집계표,
- 은평_ST93제외_10개군집_스테이션분류 : 스테이션 군집 분류 결과 파일.
### Note : 
- make_cluster.ipynb : 군집용 초기 파일
- eunpyeong_station_cluster_10_map : 군집 지도로 볼 수 있는 파일. 
  - 보는 방법 : extensions 에서 Live Server 설치하고 vsc 하단 오른쪽 Go Live 누르면 웹에서 열립니다.


# 파일트리 기준
- 기능별로 폴더 나눔.

##### 앱 전체 공통 기능
core/
├─ constants/
│  ├─ app_colors.dart
│  ├─ app_strings.dart
│  └─ api_urls.dart
├─ network/
│  ├─ api_client.dart
│  └─ auth_interceptor.dart
├─ storage/
│  ├─ secure_storage_service.dart
│  └─ local_storage_service.dart
└─ utils/
   ├─ validators.dart
   ├─ formatters.dart
   └─ role_helper.dart

API 호출, 로그인 토큰 저장, 상수 관리, 공통 유틸.

##### 공통위젯
shared/
├─ widgets/
│  ├─ custom_button.dart
│  ├─ custom_text_field.dart
│  ├─ loading_view.dart
│  ├─ error_view.dart
│  └─ responsive_scaffold.dart
└─ models/
   ├─ user_model.dart
   ├─ station_model.dart
   └─ weather_model.dart


##### 앱
features/
├─ splash/
├─ auth/
├─ map/
├─ dashboard/
├─ station/
├─ reservation/
└─ settings/

================================
- auth 
: 로그인 화면, 
  로그인 상태관리, 
  서버 로그인 요청, 
  역할 저장.
  auth/
  ├─ auth_page.dart
  ├─ auth_provider.dart
  ├─ auth_service.dart
  └─ widgets/
    └─ login_form.dart
================================
- map 
: 소비자 메인지도, 
  즐겨찾기 스테이션 표시, 
  실시간 따릉이 대수 표시, 
  마커 클릭 시 상세보기
  map/
  ├─ map_page.dart
  ├─ map_provider.dart
  ├─ map_service.dart
  ├─ widgets/
  │  ├─ station_marker.dart
  │  ├─ station_bottom_sheet.dart
  │  └─ favorite_station_card.dart
  └─ models/
    └─ map_station_model.dart
================================
- dashboard
: 관리자 대시보드,
  실시간 따릉이 대수표시,
  시간별 예측 대수표시
  dashboard/
  ├─ admin_dashboard_page.dart
  ├─ dashboard_provider.dart
  ├─ dashboard_service.dart
  ├─ widgets/
  │  ├─ summary_card.dart
  │  ├─ refill_card.dart
  │  └─ station_status_table.dart
  └─ models/
    └─ dashboard_model.dart
================================

- station
: 특정 스테이션 상세 정보
  실시간 대수,
  예측 대수,
  예약량,
  사용량,
  즐겨찾는 스테이션
  station/
  ├─ station_detail_page.dart
  ├─ station_provider.dart
  ├─ station_service.dart
  ├─ widgets/
  │  ├─ station_info_card.dart
  │  ├─ usage_chart.dart
  │  └─ reservation_info_card.dart
  └─ models/
    └─ station_detail_model.dart
================================

- reservation
: 예약 현황 (예약시간, 예약 위치)
  reservation/
  ├─ reservation_page.dart
  ├─ reservation_provider.dart
  ├─ reservation_service.dart
  ├─ widgets/
  │  ├─ reservation_button.dart
  │  └─ reservation_timer.dart
  └─ models/
    └─ reservation_model.dart
 
====================================

- settings
: 로그아웃, 사용자 정보(?), 간단한 설정.


lib/
├─ main.dart
├─ app.dart
├─ core/
│  ├─ constants/
│  │  ├─ app_colors.dart
│  │  ├─ app_strings.dart
│  │  └─ api_urls.dart
│  ├─ network/
│  │  ├─ api_client.dart
│  │  └─ auth_interceptor.dart
│  ├─ storage/
│  │  ├─ secure_storage_service.dart
│  │  └─ local_storage_service.dart
│  └─ utils/
│     ├─ validators.dart
│     ├─ formatters.dart
│     └─ role_helper.dart
├─ routes/
│  ├─ app_router.dart
│  └─ route_names.dart
├─ shared/
│  ├─ widgets/
│  │  ├─ custom_button.dart
│  │  ├─ custom_text_field.dart
│  │  ├─ loading_view.dart
│  │  ├─ error_view.dart
│  │  └─ responsive_scaffold.dart
│  └─ models/
│     ├─ user_model.dart
│     ├─ station_model.dart
│     └─ weather_model.dart
└─ features/
   ├─ splash/
   │  └─ splash_page.dart
   ├─ auth/
   │  ├─ auth_page.dart
   │  ├─ auth_provider.dart
   │  ├─ auth_service.dart
   │  └─ widgets/
   │     └─ login_form.dart
   ├─ map_for_user/
   │  ├─ map_page.dart
   │  ├─ map_provider.dart
   │  ├─ map_service.dart
   │  ├─ models/
   │  │  └─ map_station_model.dart
   │  └─ widgets/
   │     ├─ station_marker.dart
   │     ├─ station_bottom_sheet.dart
   │     └─ favorite_station_card.dart
   ├─ dashboard/
   │  ├─ worker_dashboard_page.dart
   │  ├─ admin_dashboard_page.dart
   │  ├─ dashboard_provider.dart
   │  ├─ dashboard_service.dart
   │  ├─ models/
   │  │  └─ dashboard_model.dart
   │  └─ widgets/
   │     ├─ summary_card.dart
   │     ├─ refill_card.dart
   │     └─ station_status_table.dart
   ├─ map_for_worker/
   │  ├─ station_detail_page.dart
   │  ├─ station_provider.dart
   │  ├─ station_service.dart
   │  ├─ models/
   │  │  └─ station_detail_model.dart
   │  └─ widgets/
   │     ├─ station_info_card.dart
   │     ├─ usage_chart.dart
   │     └─ reservation_info_card.dart
   ├─ reservation/
   │  ├─ reservation_page.dart
   │  ├─ reservation_provider.dart
   │  ├─ reservation_service.dart
   │  ├─ models/
   │  │  └─ reservation_model.dart
   │  └─ widgets/
   │     ├─ reservation_button.dart
   │     └─ reservation_timer.dart
   └─ settings/
      └─ settings_page.dart




- 소비자
splash_page.dart
auth_page.dart
map_for_user_page.dart
reservation_page.dart

- 기사님
map_for_worker.dart

- 관리자
admin_dashboard_page.dart

상현 : user map 폴더
다원 : 로그인 auth폴더
찬솔 : 대시보드 dashboard 폴더
신영 : worker map 폴더
광태 : 예약 reservation 폴더
혜전 : splash, ERD, workbench.