#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GRIB 파일 배치 변환 스크립트 (GeoTIFF & CSV) - Checkpoint 포함
중단된 지점부터 이어하기 위해 남은 파일 목록을 JSON으로 관리합니다.
"""

import os
import sys
import json
from pathlib import Path
from grib_parser import GRIB1Parser
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS

# 체크포인트 파일명
CHECKPOINT_FILE = Path('checkpoint.json')


def load_checkpoint():
    """체크포인트 파일에서 남은 파일 목록을 로드합니다."""
    if not CHECKPOINT_FILE.exists():
        return None

    try:
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 문자열 경로를 Path 객체로 변환하여 반환
            return [Path(p) for p in data.get('remaining_files', [])]
    except Exception as e:
        print(f"[ERROR] 체크포인트 로드 실패: {e}")
        return None


def save_checkpoint(remaining_files):
    """남은 파일 목록을 체크포인트 파일에 저장합니다."""
    try:
        # Path 객체를 문자열로 변환하여 저장
        data = {
            'remaining_files': [str(p) for p in remaining_files]
        }
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] 체크포인트 저장 실패: {e}")


def convert_to_geotiff(grib_file, output_file):
    """GRIB 파일을 GeoTIFF로 변환"""
    try:
        parser = GRIB1Parser(grib_file)
        parser.parse()

        ny = parser.metadata['ny']
        nx = parser.metadata['nx']
        data = parser.data

        # 격자 좌표 (한국 지역 근사)
        lat_start, lat_end = 43.0, 33.0
        lon_start, lon_end = 124.0, 132.0

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
        print(f"    [TIF FAIL] 변환 실패: {e}")
        return False


def convert_to_csv(grib_file, output_file):
    """GRIB 파일을 CSV로 변환"""
    try:
        parser = GRIB1Parser(grib_file)
        _, data = parser.parse()

        if data is None:
            raise ValueError("데이터를 읽을 수 없습니다.")

        lat_grid, lon_grid = parser.get_grid_coords()

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("Y,X,Latitude,Longitude,Value\n")
            ny, nx = data.shape
            for i in range(ny):
                for j in range(nx):
                    lat = lat_grid[i, j]
                    lon = lon_grid[i, j]
                    val = data[i, j]
                    f.write(f"{i},{j},{lat:.6f},{lon:.6f},{val:.6f}\n")

        return True
    except Exception as e:
        print(f"    [CSV FAIL] 변환 실패: {e}")
        return False


def main():
    """메인 함수"""
    # 1. 경로 설정
    data_dir = Path('data')
    result_tif_root = Path('result/tif')
    result_csv_root = Path('result/csv')

    if not data_dir.exists():
        print(f"[ERROR] 입력 디렉토리를 찾을 수 없습니다: {data_dir}")
        sys.exit(1)

    print(f"=" * 80)
    print(f"GRIB 배치 변환 (Checkpoint 포함)")
    print(f"=" * 80)
    print(f"입력 루트: {data_dir}")
    print(f"출력 (TIF): {result_tif_root}")
    print(f"출력 (CSV): {result_csv_root}")
    print(f"=" * 80)

    # 2. 작업 목록 초기화 (Checkpoint 확인)
    files_to_process = load_checkpoint()

    if files_to_process is not None:
        print(f"[INFO] 이전 작업 내역을 발견했습니다. ({len(files_to_process)}개 파일 남음)")
        print(f"[INFO] {CHECKPOINT_FILE}에서 이어서 시작합니다.")
    else:
        print(f"[INFO] 새로운 작업을 시작합니다. 파일 목록을 스캔합니다...")
        all_items = sorted(list(data_dir.rglob('*')))
        # 숨김 파일 제외 및 파일만 필터링
        files_to_process = [f for f in all_items if f.is_file() and not f.name.startswith('.')]

        # 초기 목록 저장
        save_checkpoint(files_to_process)
        print(f"[INFO] 총 {len(files_to_process)}개 파일이 등록되었습니다.")

    if not files_to_process:
        print(f"[WARN] 처리할 파일이 없습니다. 작업을 종료합니다.")
        # 작업이 다 끝났으면 체크포인트 파일 삭제 (선택사항)
        if CHECKPOINT_FILE.exists():
            os.remove(CHECKPOINT_FILE)
            print("[INFO] 완료된 체크포인트 파일을 삭제했습니다.")
        sys.exit(0)

    print()

    # 통계
    stats = {'success': 0, 'fail': 0}
    total_initial_count = len(files_to_process)

    # 3. 반복 처리 (while 루프 사용)
    # 리스트의 첫 번째 요소를 계속 가져오고, 성공/실패 여부와 관계없이 처리 후 리스트에서 제거
    while files_to_process:
        # 현재 처리할 파일 (리스트의 0번째)
        current_file = files_to_process[0]

        # 파일이 실제로 존재하는지 확인 (사용자가 중간에 지웠을 수도 있음)
        if not current_file.exists():
            print(f"[SKIP] 파일이 존재하지 않음: {current_file}")
            files_to_process.pop(0)
            save_checkpoint(files_to_process)
            continue

        try:
            # 경로 계산
            relative_path = current_file.relative_to(data_dir)
            tif_output_dir = result_tif_root / relative_path.parent
            csv_output_dir = result_csv_root / relative_path.parent

            tif_output_dir.mkdir(parents=True, exist_ok=True)
            csv_output_dir.mkdir(parents=True, exist_ok=True)

            base_filename = current_file.name.replace('.', '_')
            tif_path = tif_output_dir / (base_filename + '.tif')
            csv_path = csv_output_dir / (base_filename + '.csv')

            current_idx = total_initial_count - len(files_to_process) + 1
            print(f"[{current_idx}/{total_initial_count}] {relative_path}")

            # 변환 실행
            tif_ok = convert_to_geotiff(str(current_file), str(tif_path))
            csv_ok = convert_to_csv(str(current_file), str(csv_path))

            if tif_ok:
                print(f"  → TIF: [OK]")
            if csv_ok:
                print(f"  → CSV: [OK]")

            if tif_ok and csv_ok:
                stats['success'] += 1
            else:
                stats['fail'] += 1

        except Exception as e:
            print(f"  [ERROR] 처리 중 예외 발생: {e}")
            stats['fail'] += 1

        # 4. 처리 완료 후 목록에서 제거 및 체크포인트 갱신
        files_to_process.pop(0)
        save_checkpoint(files_to_process)
        print(f"  [SAVE] 체크포인트 갱신 (남은 파일: {len(files_to_process)}개)\n")

    # 결과 요약
    print(f"=" * 80)
    print(f"모든 작업이 완료되었습니다.")
    print(f"=" * 80)
    print(f"처리 성공: {stats['success']}")
    print(f"처리 실패: {stats['fail']}")

    # 완료 후 체크포인트 삭제
    if CHECKPOINT_FILE.exists():
        os.remove(CHECKPOINT_FILE)
        print(f"[INFO] 체크포인트 파일({CHECKPOINT_FILE})을 삭제했습니다.")
    print(f"=" * 80)


if __name__ == '__main__':
    main()
