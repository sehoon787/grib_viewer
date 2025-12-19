"""
GRIB 파일 뷰어
201501 폴더의 비표준 GRIB1 파일을 읽고 시각화/변환합니다.
"""
import os
import sys
import io
import argparse
from grib_parser import GRIB1Parser

# UTF-8 출력
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    import matplotlib
    matplotlib.use('TkAgg')  # Windows에서 더 안정적
except ImportError as e:
    print(f"필요한 패키지가 설치되지 않았습니다: {e}")
    print("가상환경을 활성화하고 requirements.txt를 설치하세요.")
    sys.exit(1)

# GeoTIFF 변환용
try:
    import rasterio
    from rasterio.transform import from_bounds
    from pyproj import CRS
    GEOTIFF_AVAILABLE = True
except ImportError:
    GEOTIFF_AVAILABLE = False


# 파라미터 코드 -> 이름 매핑
PARAM_NAMES = {
    11: '기온 (Temperature)',
    33: '동서바람 (U-wind)',
    34: '남북바람 (V-wind)',
    52: '상대습도 (Relative Humidity)',
    61: '1시간 강수량 (1-hr Precipitation)',
    71: '전운량 (Total Cloud Cover)',
    84: '대류운량 (Convective Cloud Cover)',
    252: '풍속 (Wind Speed)',
    253: '풍향 (Wind Direction)',
    254: '하늘상태 (Sky Condition)',
    255: '낙뢰/강수형태 (Lightning/Precip Type)',
}


def get_param_name(code):
    """파라미터 코드를 이름으로 변환"""
    return PARAM_NAMES.get(code, f'Parameter {code}')


def ensure_result_dir():
    """result 디렉토리 생성"""
    if not os.path.exists('../result'):
        os.makedirs('../result')
        print("result/ 디렉토리를 생성했습니다.")


def show_metadata(file_path):
    """메타데이터 출력"""
    parser = GRIB1Parser(file_path)
    metadata, data = parser.parse()

    print("\n" + "=" * 80)
    print("GRIB 파일 메타데이터")
    print("=" * 80)
    print(f"\n파일: {os.path.basename(file_path)}")
    print(f"GRIB 버전: {metadata['edition']}")
    print(f"총 길이: {metadata['total_length']:,} bytes")

    print(f"\n생산 정보:")
    print(f"  센터 ID: {metadata['center_id']}")
    print(f"  프로세스 ID: {metadata['process_id']}")

    print(f"\n데이터 정보:")
    param_name = get_param_name(metadata['parameter'])
    print(f"  파라미터: {param_name}")
    print(f"  레벨 타입: {metadata['level_type']}")
    print(f"  레벨 값: {metadata['level_value']}")

    if 'date' in metadata:
        print(f"  날짜/시간: {metadata['date']}")

    if 'nx' in metadata and 'ny' in metadata:
        print(f"\n격자 정보:")
        print(f"  격자 크기: {metadata['nx']} x {metadata['ny']}")
        print(f"  격자점 수: {metadata['nx'] * metadata['ny']:,}")
        print(f"  격자 타입: Lambert Conformal (type {metadata['grid_type']})")

    if data is not None:
        print(f"\n데이터 통계:")
        print(f"  최소값: {data.min():.6f}")
        print(f"  최대값: {data.max():.6f}")
        print(f"  평균값: {data.mean():.6f}")
        print(f"  표준편차: {data.std():.6f}")

    print("\n" + "=" * 80)


def show_grid_values(file_path, sample_size=10):
    """격자 단위 값 표시"""
    parser = GRIB1Parser(file_path)
    metadata, data = parser.parse()

    if data is None:
        print("데이터를 읽을 수 없습니다.")
        return

    lat_grid, lon_grid = parser.get_grid_coords()

    print("\n" + "=" * 80)
    print("격자 단위 데이터 샘플")
    print("=" * 80)

    ny, nx = data.shape
    print(f"\n격자 크기: {ny} x {nx}")
    print(f"총 격자점: {ny * nx:,}개")

    # 샘플 추출 (균등 간격)
    step_y = max(1, ny // sample_size)
    step_x = max(1, nx // sample_size)

    print(f"\n격자 값 샘플 ({sample_size}x{sample_size} 간격으로 추출):")
    print("-" * 80)
    print(f"{'Y':>4} {'X':>4} {'위도':>10} {'경도':>10} {'값':>15}")
    print("-" * 80)

    for i in range(0, ny, step_y):
        for j in range(0, nx, step_x):
            lat = lat_grid[i, j]
            lon = lon_grid[i, j]
            val = data[i, j]
            print(f"{i:4d} {j:4d} {lat:10.4f} {lon:10.4f} {val:15.6f}")

    print("-" * 80)
    print(f"\n전체 격자 데이터를 CSV나 GeoTIFF로 저장하려면:")
    print(f"  python viewer.py {file_path} --export-csv result/grid.csv")
    print(f"  python viewer.py {file_path} --export-tiff result/grid.tif")


def export_to_csv(file_path, output_file):
    """격자 데이터를 CSV로 저장"""
    ensure_result_dir()

    parser = GRIB1Parser(file_path)
    metadata, data = parser.parse()

    if data is None:
        print("데이터를 읽을 수 없습니다.")
        return

    lat_grid, lon_grid = parser.get_grid_coords()

    # CSV 파일 생성
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Y,X,Latitude,Longitude,Value\n")

        ny, nx = data.shape
        for i in range(ny):
            for j in range(nx):
                lat = lat_grid[i, j]
                lon = lon_grid[i, j]
                val = data[i, j]
                f.write(f"{i},{j},{lat:.6f},{lon:.6f},{val:.6f}\n")

    print(f"\nCSV 파일 저장 완료: {output_file}")
    print(f"  총 {ny * nx:,}개 격자점 저장")


def export_to_geotiff(file_path, output_file):
    """격자 데이터를 GeoTIFF로 저장"""
    if not GEOTIFF_AVAILABLE:
        print("GeoTIFF 변환을 위해 rasterio와 pyproj가 필요합니다.")
        print("설치: uv pip install rasterio pyproj")
        return

    ensure_result_dir()

    parser = GRIB1Parser(file_path)
    metadata, data = parser.parse()

    if data is None:
        print("데이터를 읽을 수 없습니다.")
        return

    lat_grid, lon_grid = parser.get_grid_coords()

    # 위경도 범위
    min_lon = lon_grid.min()
    max_lon = lon_grid.max()
    min_lat = lat_grid.min()
    max_lat = lat_grid.max()

    ny, nx = data.shape

    # Transform 생성 (위경도 경계 기반)
    transform = from_bounds(min_lon, min_lat, max_lon, max_lat, nx, ny)

    # WGS84 좌표계 (EPSG:4326)
    crs = CRS.from_epsg(4326)

    # GeoTIFF 저장
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

        # 메타데이터 추가
        param_name = get_param_name(metadata['parameter'])
        dst.update_tags(
            parameter=param_name,
            date=metadata.get('date', 'N/A'),
            grid_type='Lambert Conformal (approximate)',
            source='Custom GRIB1 Parser'
        )

    print(f"\nGeoTIFF 파일 저장 완료: {output_file}")
    print(f"  크기: {ny} x {nx}")
    print(f"  좌표계: WGS84 (EPSG:4326)")
    print(f"  위도 범위: {min_lat:.4f}° ~ {max_lat:.4f}°")
    print(f"  경도 범위: {min_lon:.4f}° ~ {max_lon:.4f}°")
    print(f"\n주의: 위경도 좌표는 근사값입니다.")


def visualize(file_path, output_file=None):
    """데이터 시각화"""
    if output_file:
        ensure_result_dir()

    parser = GRIB1Parser(file_path)
    metadata, data = parser.parse()

    if data is None:
        print("데이터를 읽을 수 없습니다.")
        return

    # 격자 좌표 생성
    lat_grid, lon_grid = parser.get_grid_coords()

    if lat_grid is None or lon_grid is None:
        print("격자 좌표를 생성할 수 없습니다.")
        return

    # 파라미터 이름
    param_name = get_param_name(metadata['parameter'])

    # 플롯 생성
    fig = plt.figure(figsize=(16, 10))
    gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)

    # 1. 격자 데이터 맵
    ax1 = fig.add_subplot(gs[0, :])
    im = ax1.pcolormesh(lon_grid, lat_grid, data, cmap='viridis', shading='auto')
    ax1.set_xlabel('Longitude (deg)')
    ax1.set_ylabel('Latitude (deg)')

    title = f'{param_name}'
    if 'date' in metadata:
        title += f'\n{metadata["date"]}'
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    plt.colorbar(im, ax=ax1, label='Value')

    # 2. 히스토그램
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.hist(data.flatten(), bins=50, edgecolor='black', alpha=0.7, color='skyblue')
    ax2.set_xlabel(param_name)
    ax2.set_ylabel('Frequency')
    ax2.set_title('Data Distribution', fontsize=12)
    ax2.grid(True, alpha=0.3)

    # 3. 통계 정보
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.axis('off')

    stats_text = f"""
    File: {os.path.basename(file_path)}
    Parameter: {param_name}

    Grid Info:
      Size: {metadata['ny']} x {metadata['nx']}
      Grid points: {metadata['nx'] * metadata['ny']:,}
      Grid type: Lambert Conformal

    Lat/Lon Range (approx):
      Latitude: {lat_grid.min():.2f} ~ {lat_grid.max():.2f}
      Longitude: {lon_grid.min():.2f} ~ {lon_grid.max():.2f}

    Data Statistics:
      Min: {data.min():.6f}
      Max: {data.max():.6f}
      Mean: {data.mean():.6f}
      Std Dev: {data.std():.6f}

    Time:
      {metadata.get('date', 'N/A')}

    Note: Coordinates are approximate.
    """

    ax3.text(0.05, 0.95, stats_text, transform=ax3.transAxes,
            fontsize=9, verticalalignment='top',
            fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.suptitle('GRIB File Viewer', fontsize=16, fontweight='bold')

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"\n시각화 저장: {output_file}")
    else:
        plt.show()

    plt.close()


def list_files(data_dir):
    """GRIB 파일 목록 출력"""
    if not os.path.exists(data_dir):
        print(f"디렉토리를 찾을 수 없습니다: {data_dir}")
        return

    files = [f for f in os.listdir(data_dir) if not f.endswith('.idx')]

    if not files:
        print(f"파일이 없습니다: {data_dir}")
        return

    # 파일 타입별로 그룹화
    file_groups = {}
    for filename in files:
        parts = filename.split('_')
        if len(parts) >= 4:
            # 실제 파라미터 추출
            if 'LGT' in filename:
                param = 'LGT (낙뢰)'
            elif 'PTY' in filename:
                param = 'PTY (강수형태)'
            elif 'REH' in filename:
                param = 'REH (상대습도)'
            elif 'RN1' in filename:
                param = 'RN1 (1시간 강수)'
            elif 'SKY' in filename:
                param = 'SKY (하늘상태)'
            elif 'T1H' in filename:
                param = 'T1H (기온)'
            elif 'UUU' in filename:
                param = 'UUU (동서바람)'
            elif 'VVV' in filename:
                param = 'VVV (남북바람)'
            elif 'VEC' in filename:
                param = 'VEC (풍향)'
            elif 'WSD' in filename:
                param = 'WSD (풍속)'
            else:
                param = parts[3].split('.')[0]

            if param not in file_groups:
                file_groups[param] = []
            file_groups[param].append(filename)

    print(f"\n{data_dir} 디렉토리의 GRIB 파일:")
    print("=" * 80)
    print(f"총 {len(files)}개 파일, {len(file_groups)}개 파라미터 타입\n")

    for param in sorted(file_groups.keys()):
        print(f"{param}: {len(file_groups[param])}개 파일")
        # 첫 번째 파일만 표시
        print(f"  예: {file_groups[param][0]}")

    print("\n사용 예시:")
    first_file = files[0]
    print(f"  python viewer.py {data_dir}/{first_file} -m")
    print(f"  python viewer.py {data_dir}/{first_file} --grid")
    print(f"  python viewer.py {data_dir}/{first_file} --export-tiff result/output.tif")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='GRIB 파일 뷰어 (비표준 GRIB1 지원)')
    parser.add_argument('file', nargs='?', help='GRIB 파일 경로')
    parser.add_argument('-m', '--metadata', action='store_true',
                       help='메타데이터만 출력')
    parser.add_argument('-o', '--output', help='출력 이미지 파일명 (PNG)')
    parser.add_argument('-l', '--list', metavar='DIR',
                       help='디렉토리의 GRIB 파일 목록 출력')
    parser.add_argument('--grid', action='store_true',
                       help='격자 단위 값 샘플 표시')
    parser.add_argument('--export-csv', metavar='FILE',
                       help='격자 데이터를 CSV로 저장')
    parser.add_argument('--export-tiff', metavar='FILE',
                       help='격자 데이터를 GeoTIFF로 저장')

    args = parser.parse_args()

    # 파일 목록 모드
    if args.list:
        list_files(args.list)
        return

    # 파일이 지정되지 않은 경우
    if not args.file:
        print("사용법: python viewer.py <파일경로> [옵션]")
        print("\n옵션:")
        print("  -m, --metadata          메타데이터만 출력")
        print("  -o, --output FILE       이미지 파일로 저장 (result/폴더)")
        print("  -l, --list DIR          디렉토리의 파일 목록 출력")
        print("  --grid                  격자 단위 값 샘플 표시")
        print("  --export-csv FILE       격자 데이터를 CSV로 저장")
        print("  --export-tiff FILE      격자 데이터를 GeoTIFF로 저장")
        print("\n예시:")
        print("  python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000")
        print("  python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000 -m")
        print("  python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000 --grid")
        print("  python viewer.py data/201501/DFS_ODAM_GRD_GRB1_T1H.201501010000 --export-tiff result/temp.tif")
        print("  python viewer.py -l data/201501")
        return

    # 파일 존재 확인
    if not os.path.exists(args.file):
        print(f"파일을 찾을 수 없습니다: {args.file}")
        return

    # 격자 값 표시
    if args.grid:
        show_grid_values(args.file)
        return

    # CSV 저장
    if args.export_csv:
        export_to_csv(args.file, args.export_csv)
        return

    # GeoTIFF 저장
    if args.export_tiff:
        export_to_geotiff(args.file, args.export_tiff)
        return

    # 메타데이터 출력
    show_metadata(args.file)

    # 시각화
    if not args.metadata:
        print("\n시각화 생성 중...")
        output_path = args.output
        if output_path and not output_path.startswith('result/'):
            # output 경로가 지정되었지만 result/ 아래가 아니면 자동으로 추가
            output_path = os.path.join('../result', os.path.basename(output_path))
        visualize(args.file, output_path)


if __name__ == "__main__":
    main()
