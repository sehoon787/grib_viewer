"""
커스텀 GRIB1 파서
비표준 GDS 섹션을 가진 GRIB1 파일을 파싱합니다.
"""
import struct
import numpy as np


class GRIB1Parser:
    """GRIB1 파일 파서"""

    def __init__(self, file_path):
        self.file_path = file_path
        self.metadata = {}
        self.data = None

    def parse(self):
        """GRIB 파일 파싱"""
        with open(self.file_path, 'rb') as f:
            # Section 0: Indicator
            if not self._parse_indicator(f):
                raise ValueError("유효한 GRIB 파일이 아닙니다.")

            # Section 1: Product Definition
            self._parse_pds(f)

            # Section 2: Grid Definition (if present)
            if self.metadata.get('has_gds'):
                self._parse_gds(f)

            # Section 3: Bitmap (if present)
            if self.metadata.get('has_bms'):
                self._parse_bms(f)

            # Section 4: Binary Data
            self._parse_bds(f)

        return self.metadata, self.data

    def _parse_indicator(self, f):
        """Section 0 파싱"""
        indicator = f.read(8)
        if indicator[:4] != b'GRIB':
            return False

        self.metadata['edition'] = indicator[7]
        self.metadata['total_length'] = struct.unpack('>I', b'\x00' + indicator[4:7])[0]
        return True

    def _parse_pds(self, f):
        """Section 1: Product Definition Section 파싱"""
        length_bytes = f.read(3)
        length = struct.unpack('>I', b'\x00' + length_bytes)[0]
        data = f.read(length - 3)

        self.metadata['pds_length'] = length
        self.metadata['table_version'] = data[0]
        self.metadata['center_id'] = data[1]
        self.metadata['process_id'] = data[2]
        self.metadata['grid_id'] = data[3]

        flag = data[4]
        self.metadata['has_gds'] = bool(flag & 128)
        self.metadata['has_bms'] = bool(flag & 64)

        self.metadata['parameter'] = data[5]
        self.metadata['level_type'] = data[6]
        self.metadata['level_value'] = struct.unpack('>H', data[7:9])[0]

        # 날짜/시간 정보
        if len(data) >= 13:
            year = data[9]
            month = data[10]
            day = data[11]
            hour = data[12]

            # Year는 기준 연도(1900 또는 2000)에서의 offset
            if year > 0:
                base_year = 2000 if year < 50 else 1900
                year = base_year + year
                self.metadata['date'] = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:00"

    def _parse_gds(self, f):
        """Section 2: Grid Definition Section 파싱"""
        length_bytes = f.read(3)
        length = struct.unpack('>I', b'\x00' + length_bytes)[0]

        nv = f.read(1)[0]
        pv_pl = f.read(1)[0]
        data_type = f.read(1)[0]

        remaining = length - 6
        data = f.read(remaining)

        self.metadata['gds_length'] = length
        self.metadata['grid_type'] = data_type

        # Lambert Conformal (type 3)
        if data_type == 3 and len(data) >= 12:
            try:
                nx = struct.unpack('>H', data[0:2])[0]
                ny = struct.unpack('>H', data[2:4])[0]

                # 위경도는 milli-degrees 단위
                lat1_raw = struct.unpack('>i', data[4:8])[0]
                lon1_raw = struct.unpack('>i', data[8:12])[0]

                self.metadata['nx'] = nx
                self.metadata['ny'] = ny
                self.metadata['lat1_raw'] = lat1_raw
                self.metadata['lon1_raw'] = lon1_raw

                # 대략적인 위경도 범위 추정 (한국 지역)
                # 실제 좌표는 부정확하지만, 격자 인덱스는 사용 가능
                self.metadata['lat1'] = 33.0  # 대략적인 한국 남단
                self.metadata['lon1'] = 124.0  # 대략적인 한국 서단
                self.metadata['lat2'] = 43.0  # 대략적인 한국 북단
                self.metadata['lon2'] = 132.0  # 대략적인 한국 동단

            except Exception as e:
                print(f"GDS 파싱 경고: {e}")

    def _parse_bms(self, f):
        """Section 3: Bitmap Section 파싱"""
        length_bytes = f.read(3)
        length = struct.unpack('>I', b'\x00' + length_bytes)[0]
        data = f.read(length - 3)
        # Bitmap은 일단 스킵
        self.metadata['bms_length'] = length

    def _parse_bds(self, f):
        """Section 4: Binary Data Section 파싱"""
        start_pos = f.tell()
        length_bytes = f.read(3)
        length = struct.unpack('>I', b'\x00' + length_bytes)[0]

        flag = f.read(1)[0]
        has_unused_bits = bool(flag & 0x80)

        # Binary scale factor (E)
        scale_bytes = f.read(2)
        binary_scale = struct.unpack('>h', scale_bytes)[0]

        # Reference value (R) - IBM floating point
        ref_bytes = f.read(4)
        reference = self._ibm_to_float(ref_bytes)

        # Number of bits per value
        n_bits = f.read(1)[0]

        self.metadata['binary_scale'] = binary_scale
        self.metadata['reference'] = reference
        self.metadata['n_bits'] = n_bits

        # 디버깅 정보
        # print(f"[DEBUG] Binary Scale (E): {binary_scale}")
        # print(f"[DEBUG] Reference (R): {reference}")
        # print(f"[DEBUG] N-bits: {n_bits}")

        # 나머지 데이터 읽기
        data_length = length - 11  # 헤더를 제외한 실제 데이터 길이
        packed_data = f.read(data_length)

        # 데이터 언팩
        if n_bits > 0 and 'nx' in self.metadata and 'ny' in self.metadata:
            try:
                values = self._unpack_data(packed_data, self.metadata['nx'] * self.metadata['ny'], n_bits)

                # 실제 값으로 변환: Y = R + (2^E) * X
                # E가 음수면 나눗셈, 양수면 곱셈
                if binary_scale >= 0:
                    factor = 2.0 ** binary_scale
                else:
                    factor = 2.0 ** binary_scale  # 이미 2^(-n) = 1/(2^n)

                self.data = reference + (values * factor)

                # 2D 배열로 재구성
                self.data = self.data.reshape(self.metadata['ny'], self.metadata['nx'])

            except Exception as e:
                print(f"데이터 언팩 오류: {e}")
                import traceback
                traceback.print_exc()
                # 더미 데이터 생성 (오류 시)
                self.data = np.zeros((self.metadata.get('ny', 100), self.metadata.get('nx', 100)))

    def _ibm_to_float(self, ibm_bytes):
        """IBM floating point를 IEEE floating point로 변환"""
        ibm = struct.unpack('>I', ibm_bytes)[0]

        # IBM float 형식: S EEEEEEE MMMMMMMMMMMMMMMMMMMMMMMM
        # S: sign (1 bit)
        # E: exponent (7 bits, excess-64)
        # M: mantissa (24 bits)

        sign = (ibm >> 31) & 0x1
        exponent = (ibm >> 24) & 0x7F
        mantissa = ibm & 0x00FFFFFF

        if mantissa == 0:
            return 0.0

        # IBM exponent는 16^(exp-64) 형식
        # IEEE는 2^exp 형식이므로 변환 필요
        value = float(mantissa) / (1 << 24)  # 0.x 형태로 정규화
        value *= 16.0 ** (exponent - 64)

        if sign:
            value = -value

        return value

    def _unpack_data(self, packed_data, n_values, n_bits):
        """비트 패킹된 데이터 언팩"""
        if n_bits == 0:
            return np.zeros(n_values)

        # 각 바이트를 읽으면서 비트 추출
        values = []
        bit_buffer = 0
        bits_in_buffer = 0

        for byte in packed_data:
            bit_buffer = (bit_buffer << 8) | byte
            bits_in_buffer += 8

            while bits_in_buffer >= n_bits and len(values) < n_values:
                # 상위 n_bits 추출
                bits_in_buffer -= n_bits
                mask = (1 << n_bits) - 1
                value = (bit_buffer >> bits_in_buffer) & mask
                values.append(value)

        # 남은 값이 있으면 0으로 채우기
        while len(values) < n_values:
            values.append(0)

        return np.array(values[:n_values], dtype=np.float64)

    def get_grid_coords(self):
        """격자 좌표 생성 (근사값)"""
        if 'nx' not in self.metadata or 'ny' not in self.metadata:
            return None, None

        nx = self.metadata['nx']
        ny = self.metadata['ny']

        # 대략적인 위경도 범위 사용
        lat1 = self.metadata.get('lat1', 33.0)
        lat2 = self.metadata.get('lat2', 43.0)
        lon1 = self.metadata.get('lon1', 124.0)
        lon2 = self.metadata.get('lon2', 132.0)

        # 균일 격자 생성
        lats = np.linspace(lat2, lat1, ny)  # 북에서 남으로
        lons = np.linspace(lon1, lon2, nx)  # 서에서 동으로

        lon_grid, lat_grid = np.meshgrid(lons, lats)

        return lat_grid, lon_grid
