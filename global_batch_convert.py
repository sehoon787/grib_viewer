#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GRIB 파일 배치 변환 스크립트 (GeoTIFF & CSV) - Checkpoint 포함 & 병렬 처리
중단된 지점부터 이어하기 위해 남은 파일 목록을 JSON으로 관리합니다.
멀티프로세싱을 통해 여러 파일을 동시에 처리합니다.
"""

import os
import sys
import json
from pathlib import Path
from grib_parser import GRIB1Parser
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from multiprocessing import Pool, cpu_count
from concurrent.futures import ThreadPoolExecutor
import time

# 체크포인트 파일명
CHECKPOINT_FILE = Path('checkpoint.json')

# 전역 설정 (워커 프로세스에서 사용)
DATA_DIR = None
RESULT_TIF_ROOT = None
RESULT_CSV_ROOT = None


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


def process_single_file(file_path):
    """
    단일 파일을 처리하는 워커 함수 (병렬 처리용)

    Args:
        file_path: 처리할 GRIB 파일 경로 (Path 객체 또는 문자열)

    Returns:
        dict: {'file': Path, 'success': bool, 'tif_ok': bool, 'csv_ok': bool, 'error': str}
    """
    global DATA_DIR, RESULT_TIF_ROOT, RESULT_CSV_ROOT

    current_file = Path(file_path)
    result = {
        'file': current_file,
        'success': False,
        'tif_ok': False,
        'csv_ok': False,
        'error': None
    }

    try:
        # 파일 존재 확인
        if not current_file.exists():
            result['error'] = '파일이 존재하지 않음'
            return result

        # 경로 계산
        relative_path = current_file.relative_to(DATA_DIR)
        tif_output_dir = RESULT_TIF_ROOT / relative_path.parent
        csv_output_dir = RESULT_CSV_ROOT / relative_path.parent

        tif_output_dir.mkdir(parents=True, exist_ok=True)
        csv_output_dir.mkdir(parents=True, exist_ok=True)

        base_filename = current_file.name.replace('.', '_')
        tif_path = tif_output_dir / (base_filename + '.tif')
        csv_path = csv_output_dir / (base_filename + '.csv')

        # TIF와 CSV 변환을 스레드로 병렬 처리
        with ThreadPoolExecutor(max_workers=2) as executor:
            tif_future = executor.submit(convert_to_geotiff, str(current_file), str(tif_path))
            csv_future = executor.submit(convert_to_csv, str(current_file), str(csv_path))

            result['tif_ok'] = tif_future.result()
            result['csv_ok'] = csv_future.result()

        result['success'] = result['tif_ok'] and result['csv_ok']

    except Exception as e:
        result['error'] = str(e)

    return result


def init_worker(data_dir, result_tif_root, result_csv_root):
    """워커 프로세스 초기화 함수"""
    global DATA_DIR, RESULT_TIF_ROOT, RESULT_CSV_ROOT
    DATA_DIR = data_dir
    RESULT_TIF_ROOT = result_tif_root
    RESULT_CSV_ROOT = result_csv_root


def main():
    """메인 함수 (병렬 처리)"""
    # 1. 경로 설정
    data_dir = Path('data')
    result_tif_root = Path('result/tif')
    result_csv_root = Path('result/csv')

    if not data_dir.exists():
        print(f"[ERROR] 입력 디렉토리를 찾을 수 없습니다: {data_dir}")
        sys.exit(1)

    # CPU 코어 수 확인
    num_workers = cpu_count()
    print(f"=" * 80)
    print(f"GRIB 배치 변환 (병렬 처리 & Checkpoint 포함)")
    print(f"=" * 80)
    print(f"입력 루트: {data_dir}")
    print(f"출력 (TIF): {result_tif_root}")
    print(f"출력 (CSV): {result_csv_root}")
    print(f"병렬 워커: {num_workers}개 프로세스")
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
    processed_count = 0
    start_time = time.time()

    # 배치 크기 설정 (체크포인트 저장 주기)
    batch_size = num_workers * 2  # 워커 수의 2배 단위로 체크포인트 저장

    # 3. 병렬 처리
    print(f"[INFO] 병렬 처리 시작 (배치 크기: {batch_size})\n")

    try:
        # 프로세스 풀 생성
        with Pool(processes=num_workers, initializer=init_worker,
                  initargs=(data_dir, result_tif_root, result_csv_root)) as pool:

            # 배치 단위로 처리
            while files_to_process:
                # 현재 배치 추출
                current_batch = files_to_process[:batch_size]
                batch_start = processed_count + 1

                # 배치 병렬 처리
                results = pool.map(process_single_file, current_batch)

                # 결과 처리 및 출력
                for idx, result in enumerate(results):
                    current_idx = batch_start + idx
                    relative_path = result['file'].relative_to(data_dir)

                    print(f"[{current_idx}/{total_initial_count}] {relative_path}")

                    if result['error']:
                        print(f"  [ERROR] {result['error']}")
                        stats['fail'] += 1
                    else:
                        if result['tif_ok']:
                            print(f"  → TIF: [OK]")
                        if result['csv_ok']:
                            print(f"  → CSV: [OK]")

                        if result['success']:
                            stats['success'] += 1
                        else:
                            stats['fail'] += 1

                # 배치 처리 완료 - 체크포인트 업데이트
                processed_count += len(current_batch)
                files_to_process = files_to_process[len(current_batch):]
                save_checkpoint(files_to_process)

                elapsed = time.time() - start_time
                avg_time = elapsed / processed_count if processed_count > 0 else 0
                remaining = len(files_to_process)
                eta = avg_time * remaining if avg_time > 0 else 0

                print(f"\n[BATCH COMPLETE] 처리: {processed_count}/{total_initial_count} | "
                      f"남은 파일: {remaining}개 | "
                      f"경과 시간: {elapsed:.1f}초 | "
                      f"예상 남은 시간: {eta:.1f}초\n")

    except KeyboardInterrupt:
        print(f"\n\n[INTERRUPT] 사용자가 작업을 중단했습니다.")
        print(f"[INFO] 체크포인트가 저장되었습니다. 다음에 이어서 실행할 수 있습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 병렬 처리 중 오류 발생: {e}")
        save_checkpoint(files_to_process)
        sys.exit(1)

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
