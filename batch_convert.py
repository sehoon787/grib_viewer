#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GRIB 파일 배치 GeoTIFF 변환 스크립트
data/201501 디렉토리의 모든 GRIB 파일을 GeoTIFF로 변환
"""

import os
import sys
from pathlib import Path
from grib_parser import GRIB1Parser
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS


def ensure_result_dir():
    """result 디렉토리 생성"""
    if not os.path.exists('result'):
        os.makedirs('result')


def convert_to_geotiff(grib_file, output_file):
    """GRIB 파일을 GeoTIFF로 변환"""
    try:
        parser = GRIB1Parser(grib_file)
        parser.parse()  # 파일 파싱

        # 격자 정보
        ny = parser.metadata['ny']
        nx = parser.metadata['nx']

        # 데이터는 이미 2D 배열 형태
        data = parser.data

        # 격자 좌표 (한국 지역 근사)
        lat_start, lat_end = 43.0, 33.0
        lon_start, lon_end = 124.0, 132.0

        # GeoTIFF 저장
        transform = from_bounds(lon_start, lat_end, lon_end, lat_start, nx, ny)
        crs = CRS.from_epsg(4326)

        with rasterio.open(
            output_file,
            'w',
            driver='GTiff',
            height=ny,
            width=nx,
            count=1,
            dtype=data.dtype,
            crs=crs,
            transform=transform,
            compress='lzw'
        ) as dst:
            dst.write(data, 1)

        return True
    except Exception as e:
        print(f"  [FAIL] 변환 실패: {e}")
        return False


def main():
    """메인 함수"""
    data_dir = Path('data/201501')

    if not data_dir.exists():
        print(f"[ERROR] 디렉토리를 찾을 수 없습니다: {data_dir}")
        sys.exit(1)

    # GRIB 파일 목록
    grib_files = sorted(list(data_dir.glob('DFS_ODAM_GRD_GRB1_*')))

    if not grib_files:
        print(f"[ERROR] GRIB 파일을 찾을 수 없습니다: {data_dir}")
        sys.exit(1)

    total_files = len(grib_files)
    print(f"=" * 80)
    print(f"GRIB → GeoTIFF 배치 변환")
    print(f"=" * 80)
    print(f"입력 디렉토리: {data_dir}")
    print(f"출력 디렉토리: result/")
    print(f"총 파일 수: {total_files}개")
    print(f"=" * 80)
    print()

    # result 디렉토리 생성
    ensure_result_dir()

    # 통계
    success_count = 0
    fail_count = 0

    # 배치 변환
    for idx, grib_file in enumerate(grib_files, 1):
        filename = grib_file.name
        output_filename = filename.replace('.201501', '_201501') + '.tif'
        output_file = Path('result') / output_filename

        print(f"[{idx}/{total_files}] {filename}")
        print(f"  → {output_filename}")

        if convert_to_geotiff(str(grib_file), str(output_file)):
            file_size = output_file.stat().st_size / 1024  # KB
            print(f"  [OK] 완료 ({file_size:.1f} KB)")
            success_count += 1
        else:
            fail_count += 1

        print()

    # 결과 요약
    print(f"=" * 80)
    print(f"변환 완료")
    print(f"=" * 80)
    print(f"[성공] {success_count}개")
    print(f"[실패] {fail_count}개")
    print(f"[출력] result/")
    print(f"=" * 80)


if __name__ == '__main__':
    main()
