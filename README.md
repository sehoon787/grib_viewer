# GRIB Viewer - 비표준 GRIB1 파일 뷰어

data/201501 폴더의 비표준 GRIB1 형식 파일을 읽고 시각화하는 Python 도구입니다.

## 특징

- **커스텀 GRIB1 파서**: 불완전한 GDS 섹션을 가진 비표준 GRIB1 파일 지원
- **IBM Float 변환**: IBM floating point 형식의 Reference 값 자동 변환
- **데이터 시각화**: 격자 맵, 히스토그램, 통계 정보 제공
- **다양한 기상 요소**: 기온, 풍속, 습도, 강수 등 10종류의 파라미터 지원

## 설치

```bash
# 가상환경 생성
uv venv

# 가상환경 활성화 (Windows)
.venv\Scripts\activate

# 패키지 설치
uv pip install -r requirements.txt
```

## 사용법

### 1. 파일 목록 보기

```bash
python viewer.py -l data/201501
```

### 2. 메타데이터 확인

```bash
python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000 -m
```

### 3. 격자 단위 값 확인

```bash
python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000 --grid
```

출력 예시:
```
격자 크기: 253 x 149
총 격자점: 37,697개

격자 값 샘플 (10x10 간격):
   Y    X    위도      경도         값
   0    0  43.0000  124.0000  -500.000000
  75   56  40.0238  127.0270   -43.000000
 100   70  39.0317  127.7838   -73.000000
```

### 4. 데이터 시각화

```bash
# 화면에 표시
python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000

# PNG 파일로 저장 (result/ 폴더)
python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000 -o result/temp.png
```

### 5. GeoTIFF 변환

```bash
python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000 --export-tiff result/temp.tif
```

출력:
```
GeoTIFF 파일 저장 완료: result/temp.tif
  크기: 253 x 149
  좌표계: WGS84 (EPSG:4326)
  위도 범위: 33.0000° ~ 43.0000°
  경도 범위: 124.0000° ~ 132.0000°
```

### 6. CSV 저장

```bash
python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000 --export-csv result/grid.csv
```

CSV 형식:
```
Y,X,Latitude,Longitude,Value
0,0,43.0000,124.0000,-500.000000
0,1,43.0000,124.0541,-500.000000
...
```

### 7. 배치 GeoTIFF 변환

data/201501 디렉토리의 모든 GRIB 파일을 한 번에 GeoTIFF로 변환합니다.

```bash
python batch_convert.py
```

출력 예시:
```
================================================================================
GRIB → GeoTIFF 배치 변환
================================================================================
입력 디렉토리: data\201501
출력 디렉토리: result/
총 파일 수: 227개
================================================================================

[1/227] DFS_ODAM_GRD_GRB1_LGT.201501010000
  → DFS_ODAM_GRD_GRB1_LGT_201501010000.tif
  [OK] 완료 (16.7 KB)

[2/227] DFS_ODAM_GRD_GRB1_LGT.201501010300
  → DFS_ODAM_GRD_GRB1_LGT_201501010300.tif
  [OK] 완료 (16.7 KB)
...

================================================================================
변환 완료
================================================================================
[성공] 227개
[실패] 0개
[출력] result/
================================================================================
```

변환 결과:
- 총 227개 GeoTIFF 파일 생성
- result/ 디렉토리에 저장 (약 8.6MB)
- 각 파일 크기: 16~36KB (LZW 압축)
- WGS84 (EPSG:4326) 좌표계
- 253×149 격자 (37,697 픽셀)

## 파일 구조

```
grib_viewer/
├── data/
│   └── 201501/           # GRIB 파일 디렉토리 (227개)
├── result/               # 출력 파일 저장 디렉토리 (자동 생성)
│   ├── *.tif            # GeoTIFF 파일
│   ├── *.png            # 시각화 이미지
│   └── *.csv            # 격자 데이터 CSV
├── grib_parser.py        # 커스텀 GRIB1 파서
├── viewer.py             # 메인 뷰어 스크립트
├── batch_convert.py      # 배치 GeoTIFF 변환 스크립트
├── requirements.txt      # Python 패키지 목록
└── README.md             # 문서
```

## 지원하는 기상 요소

| 코드 | 설명 | 파일 예시 |
|------|------|-----------|
| T1H  | 기온 (Temperature) | DFS_ODAM_GRD_GRB1_T1H.* |
| REH  | 상대습도 (Relative Humidity) | DFS_ODAM_GRD_GRB1_REH.* |
| RN1  | 1시간 강수량 | DFS_ODAM_GRD_GRB1_RN1.* |
| WSD  | 풍속 (Wind Speed) | DFS_ODAM_GRD_GRB1_WSD.* |
| VEC  | 풍향 (Wind Direction) | DFS_ODAM_GRD_GRB1_VEC.* |
| UUU  | 동서바람 (U-component) | DFS_ODAM_GRD_GRB1_UUU.* |
| VVV  | 남북바람 (V-component) | DFS_ODAM_GRD_GRB1_VVV.* |
| SKY  | 하늘상태 (Sky Condition) | DFS_ODAM_GRD_GRB1_SKY.* |
| PTY  | 강수형태 (Precipitation Type) | DFS_ODAM_GRD_GRB1_PTY.* |
| LGT  | 낙뢰 (Lightning) | DFS_ODAM_GRD_GRB1_LGT.* |

## 주요 기능

### 1. GRIB1 파서 (grib_parser.py)

- Section 0-4 완전 파싱
- IBM floating point 자동 변환
- 비트 패킹된 데이터 언팩
- 불완전한 GDS 섹션 처리
- 근사 위경도 좌표 생성

### 2. 데이터 뷰어 (viewer.py)

**시각화:**
- 격자 데이터 2D 맵
- 데이터 분포 히스토그램
- 통계 정보 (최소/최대/평균/표준편차)
- PNG 파일 저장 (result/ 폴더)

**격자 단위 보기:**
- 격자 인덱스별 값 표시
- 위도/경도 좌표와 함께 출력
- 샘플링 간격 조정 가능

**데이터 변환:**
- **GeoTIFF 변환**: WGS84 좌표계, LZW 압축
- **CSV 저장**: 전체 격자 데이터 (Y, X, Lat, Lon, Value)
- 메타데이터 포함 저장

## 파일 형식 정보

### 문제점

이 GRIB 파일들은 비표준 형식입니다:

- **GDS 길이**: 34 bytes (표준: 48 bytes 이상)
- **누락된 정보**: Latin1, Latin2 (Lambert Conformal 표준 위도)
- **결과**: 표준 GRIB 라이브러리(cfgrib, pygrib)로 읽을 수 없음

### 해결 방법

커스텀 파서로 다음을 처리합니다:

1. 불완전한 GDS 섹션 허용
2. 누락된 위경도 정보는 근사값 사용 (한국 지역 가정)
3. IBM float 형식 자동 변환
4. 비트 패킹 데이터 언팩

## 데이터 해석

일부 파라미터는 스케일이 적용되어 있을 수 있습니다:

- 기온: 값 * 0.1 = 실제 온도(°C)
  예: -500 → -50.0°C
- 습도: 값 * 0.1 = 실제 습도(%)
- 풍속: 값 * 0.1 = 실제 풍속(m/s)

**주의**: 정확한 스케일은 데이터 제공처에 확인이 필요합니다.

## 한계점

1. **위경도 좌표**: 근사값이며, 정확한 Lambert Conformal 투영이 아닙니다.
2. **데이터 스케일**: 일부 파라미터의 정확한 스케일이 불명확합니다.
3. **한글 폰트**: matplotlib 기본 폰트가 한글을 지원하지 않아 경고가 발생합니다 (기능 정상).

## 트러블슈팅

### 패키지 설치 오류

```bash
# uv가 없는 경우
pip install uv

# 재설치
uv pip install --force-reinstall -r requirements.txt
```

### 한글 폰트 경고

matplotlib의 한글 폰트 경고는 무시해도 됩니다. 시각화는 정상 작동합니다.

## 테스트 예시

```bash
# 기온 데이터 시각화
python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000 -o temp.png

# 풍속 데이터 확인
python viewer.py data/201501/DFS_ODAM_GRD_GRB1_WSD.201501010000 -m

# 강수량 시각화
python viewer.py data/201501/DFS_ODAM_GRD_GRB1_RN1.201501010000
```

## 기술 스택

- **Python 3.10+**
- **NumPy**: 수치 계산
- **Matplotlib**: 시각화
- **커스텀 GRIB1 파서**: 비표준 형식 지원

## 요약

이 뷰어는 data/201501 폴더의 비표준 GRIB1 파일을 읽고 시각화할 수 있습니다.
표준 라이브러리로는 읽을 수 없는 파일이지만, 커스텀 파서를 통해 데이터를 추출하고
근사 좌표를 사용하여 시각화합니다.

**성공적으로 작동**: 메타데이터 확인, 데이터 추출, 시각화 모두 가능합니다.
